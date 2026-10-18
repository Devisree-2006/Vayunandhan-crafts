"""
Notification services: Email + WhatsApp Business Cloud API.

Design principles:
  - Every notification attempt is recorded in NotificationLog with an
    idempotency_key so it is never sent twice for the same event.
  - Failures are logged and retried without crashing the order flow.
  - WhatsApp and email failures never prevent order confirmation.
  - Credentials missing → status = 'skipped', clear log message.
"""
import hashlib
import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

import requests

from notifications.models import NotificationLog
from orders.models import Order

logger = logging.getLogger(__name__)

# ── Idempotency key ───────────────────────────────────────────────────────────────

def _idem_key(order_ref: str, event: str, channel: str) -> str:
    raw = f'{order_ref}:{event}:{channel}'
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


# ── Main dispatch ─────────────────────────────────────────────────────────────────

def send_order_notifications(order: Order, event: str):
    """
    Entry point called after significant order events.
    Sends both email and WhatsApp notifications where configured and enabled.
    Always returns without raising — failures are logged.
    """
    store = _get_store_settings()

    _dispatch_email(order, event, store)
    _dispatch_whatsapp(order, event, store)


# ── Email ─────────────────────────────────────────────────────────────────────────

_EMAIL_EVENTS = {
    NotificationLog.EVENT_ORDER_PLACED,
    NotificationLog.EVENT_PAYMENT_CONFIRMED,
    NotificationLog.EVENT_PAYMENT_VERIFICATION_PENDING,
    NotificationLog.EVENT_PAYMENT_REJECTED,
    NotificationLog.EVENT_ORDER_DISPATCHED,
    NotificationLog.EVENT_ORDER_DELIVERED,
    NotificationLog.EVENT_ORDER_CANCELLED,
    NotificationLog.EVENT_REFUNDED,
}

_EMAIL_SUBJECTS = {
    NotificationLog.EVENT_ORDER_PLACED:                    'Order Placed – {store} – {ref}',
    NotificationLog.EVENT_PAYMENT_CONFIRMED:               'Order Confirmed – {store} – {ref}',
    NotificationLog.EVENT_PAYMENT_VERIFICATION_PENDING:    'Payment Received – Verification Pending – {ref}',
    NotificationLog.EVENT_PAYMENT_REJECTED:                'Payment Not Verified – {ref}',
    NotificationLog.EVENT_ORDER_DISPATCHED:                'Your Order is Dispatched! – {ref}',
    NotificationLog.EVENT_ORDER_DELIVERED:                 'Order Delivered – Thank You! – {ref}',
    NotificationLog.EVENT_ORDER_CANCELLED:                 'Order Cancelled – {ref}',
    NotificationLog.EVENT_REFUNDED:                        'Refund Processed – {ref}',
}

_EMAIL_TEMPLATES = {
    NotificationLog.EVENT_ORDER_PLACED:                 'emails/order_confirmation.html',
    NotificationLog.EVENT_PAYMENT_CONFIRMED:            'emails/order_confirmation.html',
    NotificationLog.EVENT_PAYMENT_VERIFICATION_PENDING: 'emails/payment_verification_pending.html',
    NotificationLog.EVENT_PAYMENT_REJECTED:             'emails/payment_rejected.html',
    NotificationLog.EVENT_ORDER_DISPATCHED:             'emails/order_dispatched.html',
    NotificationLog.EVENT_ORDER_DELIVERED:              'emails/order_delivered.html',
    NotificationLog.EVENT_ORDER_CANCELLED:              'emails/order_cancelled.html',
    NotificationLog.EVENT_REFUNDED:                     'emails/order_refunded.html',
}


def _dispatch_email(order: Order, event: str, store):
    if event not in _EMAIL_EVENTS:
        return

    recipient = order.customer_email
    ikey = _idem_key(order.reference, event, NotificationLog.CHANNEL_EMAIL)

    log, created = NotificationLog.objects.get_or_create(
        idempotency_key=ikey,
        defaults={
            'order':     order,
            'channel':   NotificationLog.CHANNEL_EMAIL,
            'event':     event,
            'recipient': recipient,
            'status':    NotificationLog.STATUS_PENDING,
        },
    )
    if not created and log.status == NotificationLog.STATUS_SENT:
        logger.info('Email already sent for %s / %s — skipping.', order.reference, event)
        return

    log.attempts += 1
    log.save(update_fields=['attempts', 'updated_at'])

    template = _EMAIL_TEMPLATES.get(event, 'emails/order_confirmation.html')
    subject_tpl = _EMAIL_SUBJECTS.get(event, 'Update from {store} – {ref}')
    subject = subject_tpl.format(store=store.store_name, ref=order.reference)

    # Build context
    payment = order.payments.order_by('-created_at').first()
    logo_url = None
    if store.logo:
        try:
            logo_url = store.logo.url
        except Exception:
            pass

    ctx = {
        'order':                order,
        'payment':              payment,
        'payment_method_display': payment.get_method_display() if payment else '',
        'payment_pending':      payment and payment.status != payment.STATUS_VERIFIED,
        'store_name':           store.store_name,
        'store_phone':          store.phone or store.whatsapp_number,
        'store_url':            'https://vayunandhan.com',
        'track_url':            f'https://vayunandhan.com/orders/track/?ref={order.reference}&email={order.customer_email}',
        'logo_url':             logo_url,
        'event':                event,
    }

    try:
        html_body = render_to_string(template, ctx)
    except Exception as e:
        logger.error('Email template render error (%s): %s', template, e)
        # Fall back to plain-text
        html_body = None

    plain_body = (
        f'Hi {order.customer_name},\n\n'
        f'Order ID: {order.reference}\n'
        f'Status: {order.get_status_display()}\n'
        f'Total: ₹{order.total_amount}\n\n'
        f'Thank you for shopping with {store.store_name}!\n'
    )

    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=plain_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        if html_body:
            msg.attach_alternative(html_body, 'text/html')
        msg.send()

        log.status  = NotificationLog.STATUS_SENT
        log.sent_at = timezone.now()
        log.save(update_fields=['status', 'sent_at', 'updated_at'])
        logger.info('Email sent: %s / %s → %s', order.reference, event, recipient)

    except Exception as e:
        log.status        = NotificationLog.STATUS_FAILED
        log.error_message = str(e)[:500]
        log.save(update_fields=['status', 'error_message', 'updated_at'])
        logger.error('Email failed: %s / %s — %s', order.reference, event, e)


# ── WhatsApp Business Cloud API ───────────────────────────────────────────────────

WHATSAPP_API_URL = 'https://graph.facebook.com/v19.0/{phone_number_id}/messages'

_WA_EVENTS = {
    NotificationLog.EVENT_ORDER_PLACED,
    NotificationLog.EVENT_PAYMENT_CONFIRMED,
    NotificationLog.EVENT_PAYMENT_VERIFICATION_PENDING,
    NotificationLog.EVENT_ORDER_DISPATCHED,
}


def _dispatch_whatsapp(order: Order, event: str, store):
    """Send a WhatsApp template message to the business number."""
    if event not in _WA_EVENTS:
        return

    # Check notification toggles on store settings
    if event == NotificationLog.EVENT_ORDER_PLACED and not store.notify_order_created:
        return
    if event == NotificationLog.EVENT_PAYMENT_CONFIRMED and not store.notify_payment_confirmed:
        return
    if event == NotificationLog.EVENT_ORDER_DISPATCHED and not store.notify_order_dispatched:
        return

    business_number = store.whatsapp_number or settings.STORE_WHATSAPP_NUMBER
    if not business_number:
        logger.info('STORE_WHATSAPP_NUMBER not configured — skipping WA notification.')
        return

    access_token    = settings.WHATSAPP_ACCESS_TOKEN
    phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID

    ikey = _idem_key(order.reference, event, NotificationLog.CHANNEL_WHATSAPP)
    log, created = NotificationLog.objects.get_or_create(
        idempotency_key=ikey,
        defaults={
            'order':     order,
            'channel':   NotificationLog.CHANNEL_WHATSAPP,
            'event':     event,
            'recipient': business_number,
            'status':    NotificationLog.STATUS_PENDING,
        },
    )
    if not created and log.status == NotificationLog.STATUS_SENT:
        return

    if not access_token or not phone_number_id:
        log.status        = NotificationLog.STATUS_SKIPPED
        log.error_message = 'WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID not configured.'
        log.save(update_fields=['status', 'error_message', 'updated_at'])
        logger.info('WhatsApp not configured — notification skipped for %s.', order.reference)
        return

    log.attempts += 1
    log.save(update_fields=['attempts', 'updated_at'])

    payment = order.payments.order_by('-created_at').first()
    items_text = ', '.join(
        f'{i.product_name} ×{i.quantity}' for i in order.items.all()
    )

    # Build the message body text (free-form for business-initiated within 24h window
    # OR use an approved template. Adjust template name to your approved template.)
    body_text = _build_wa_message(order, event, payment, items_text)

    # We use a text message (free-form). For template messages outside 24h window,
    # change to template message type and use your approved template name.
    payload = {
        'messaging_product': 'whatsapp',
        'to': business_number,
        'type': 'text',
        'text': {'body': body_text},
    }

    url = WHATSAPP_API_URL.format(phone_number_id=phone_number_id)
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type':  'application/json',
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        log.status  = NotificationLog.STATUS_SENT
        log.sent_at = timezone.now()
        log.save(update_fields=['status', 'sent_at', 'updated_at'])
        logger.info('WhatsApp sent: %s / %s', order.reference, event)

    except requests.exceptions.HTTPError as e:
        _handle_wa_error(log, f'HTTP {e.response.status_code}: {e.response.text[:300]}')
    except requests.exceptions.RequestException as e:
        _handle_wa_error(log, str(e)[:400])


def _build_wa_message(order, event, payment, items_text: str) -> str:
    status_map = {
        NotificationLog.EVENT_ORDER_PLACED:                 '🆕 NEW ORDER',
        NotificationLog.EVENT_PAYMENT_CONFIRMED:            '✅ PAYMENT CONFIRMED',
        NotificationLog.EVENT_PAYMENT_VERIFICATION_PENDING: '⏳ UPI PAYMENT PENDING VERIFICATION',
        NotificationLog.EVENT_ORDER_DISPATCHED:             '🚚 ORDER DISPATCHED',
    }
    header = status_map.get(event, '📦 ORDER UPDATE')
    method = payment.get_method_display() if payment else 'N/A'
    pay_status = payment.get_status_display() if payment else 'N/A'

    return (
        f'{header}\n\n'
        f'Order ID: {order.reference}\n'
        f'Customer: {order.customer_name}\n'
        f'Phone: {order.customer_phone}\n'
        f'Items: {items_text}\n'
        f'Total: ₹{order.total_amount}\n'
        f'Payment: {method} — {pay_status}\n'
        f'City: {order.city}, {order.pincode}\n'
        f'Time: {order.created_at.strftime("%d %b %Y %I:%M %p")}'
    )


def _handle_wa_error(log: NotificationLog, error_msg: str):
    log.status        = NotificationLog.STATUS_FAILED
    log.error_message = error_msg
    log.save(update_fields=['status', 'error_message', 'updated_at'])
    logger.error('WhatsApp failed for %s: %s', log.order.reference, error_msg)


# ── WhatsApp webhook verification (Meta challenge) ────────────────────────────────

def verify_whatsapp_webhook(request) -> bool:
    """
    Respond to Meta's GET challenge during webhook registration.
    Returns True if the verify token matches.
    """
    mode       = request.GET.get('hub.mode')
    token      = request.GET.get('hub.verify_token')
    challenge  = request.GET.get('hub.challenge')
    expected   = settings.WHATSAPP_VERIFY_TOKEN
    return (mode == 'subscribe' and token == expected), challenge


# ── Helper ────────────────────────────────────────────────────────────────────────

def _get_store_settings():
    from store.models import StoreSettings
    return StoreSettings.get()
