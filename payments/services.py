"""
Payment services:
  - Razorpay order creation and signature verification
  - Manual UPI payment submission and admin verification
  - Idempotent payment confirmation
"""
import hashlib
import hmac
import logging
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from orders.models import Order, OrderStatusHistory
from payments.models import Payment, UpiPaymentDetail
from store.models import StockMovement

logger = logging.getLogger(__name__)


# ── Razorpay ──────────────────────────────────────────────────────────────────────

def get_razorpay_client():
    """Return an authenticated Razorpay client, or None if not configured."""
    if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
        logger.warning('Razorpay credentials not configured.')
        return None
    try:
        import razorpay
        return razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    except ImportError:
        logger.error('razorpay package not installed.')
        return None


def create_razorpay_order(payment: Payment) -> dict:
    """
    Create a Razorpay order for the given Payment record.
    Returns the Razorpay order dict, or raises RuntimeError.
    """
    client = get_razorpay_client()
    if client is None:
        raise RuntimeError('Razorpay is not configured. Add RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to your .env.')

    amount_paise = int(payment.amount * 100)   # Razorpay works in paise
    rz_order = client.order.create({
        'amount':   amount_paise,
        'currency': 'INR',
        'receipt':  payment.order.reference,
        'notes': {
            'order_reference': payment.order.reference,
            'customer_email':  payment.order.customer_email,
        },
    })

    payment.razorpay_order_id = rz_order['id']
    payment.save(update_fields=['razorpay_order_id', 'updated_at'])

    return rz_order


def verify_razorpay_signature(razorpay_order_id: str,
                               razorpay_payment_id: str,
                               razorpay_signature: str) -> bool:
    """Verify the HMAC-SHA256 signature from Razorpay checkout."""
    key    = settings.RAZORPAY_KEY_SECRET
    if not key:
        return False
    msg    = f'{razorpay_order_id}|{razorpay_payment_id}'
    expected = hmac.new(
        key.encode('utf-8'),
        msg.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


def verify_razorpay_webhook_signature(request_body: bytes, signature: str) -> bool:
    """Verify the X-Razorpay-Signature header on a webhook."""
    secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not secret:
        return False
    expected = hmac.new(
        secret.encode('utf-8'),
        request_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@transaction.atomic
def confirm_razorpay_payment(razorpay_order_id: str,
                              razorpay_payment_id: str,
                              razorpay_signature: str,
                              event_id: str = '') -> Payment:
    """
    Idempotently confirm a Razorpay payment after signature verification.
    Raises ValueError on bad signature or if the payment is not found.
    Returns the Payment object (already verified, or now verified).
    """
    try:
        payment = Payment.objects.select_for_update().get(
            razorpay_order_id=razorpay_order_id,
            method=Payment.METHOD_RAZORPAY,
        )
    except Payment.DoesNotExist:
        raise ValueError(f'No payment found for Razorpay order {razorpay_order_id}')

    # Idempotency: already processed
    if payment.status == Payment.STATUS_VERIFIED:
        logger.info('Payment %s already verified — skipping.', payment.pk)
        return payment

    # Duplicate webhook guard
    if event_id and payment.last_webhook_event_id == event_id:
        logger.info('Duplicate webhook event %s — skipping.', event_id)
        return payment

    if not verify_razorpay_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        payment.status = Payment.STATUS_FAILED
        payment.save(update_fields=['status', 'updated_at'])
        raise ValueError('Razorpay signature verification failed.')

    # Mark payment verified
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature  = razorpay_signature
    payment.status              = Payment.STATUS_VERIFIED
    payment.verified_at         = timezone.now()
    if event_id:
        payment.last_webhook_event_id = event_id
    payment.save()

    # Update order status
    order = payment.order
    if order.status in (Order.STATUS_PLACED, Order.STATUS_PAYMENT_PENDING):
        _advance_order_to_verified(order)

    return payment


# ── Manual UPI ────────────────────────────────────────────────────────────────────

@transaction.atomic
def submit_upi_payment(payment: Payment,
                        upi_transaction_id: str,
                        screenshot=None) -> UpiPaymentDetail:
    """
    Record customer-submitted UPI transaction details.
    Does NOT verify or approve payment — only stores for admin review.
    """
    detail, created = UpiPaymentDetail.objects.get_or_create(
        payment=payment,
        defaults={
            'upi_transaction_id': upi_transaction_id.strip(),
            'screenshot': screenshot,
        }
    )
    if not created:
        # Update if re-submitted
        detail.upi_transaction_id = upi_transaction_id.strip()
        if screenshot:
            detail.screenshot = screenshot
        detail.save()

    # Move payment status to verification pending
    if payment.status == Payment.STATUS_PENDING:
        payment.status = Payment.STATUS_VERIFICATION_PENDING
        payment.save(update_fields=['status', 'updated_at'])

    # Update order status
    order = payment.order
    if order.status == Order.STATUS_PLACED:
        old_status = order.status
        order.status = Order.STATUS_PAYMENT_VERIFICATION_PENDING
        order.save(update_fields=['status', 'updated_at'])
        OrderStatusHistory.objects.create(
            order=order,
            from_status=old_status,
            to_status=order.status,
            note='Customer submitted UPI transaction details.',
        )

    return detail


@transaction.atomic
def approve_upi_payment(payment: Payment, admin_user, note: str = '') -> Payment:
    """
    Admin action: verify and approve a manual UPI payment.
    This is the ONLY way a manual UPI payment should be marked as paid.
    """
    if payment.status == Payment.STATUS_VERIFIED:
        return payment  # already approved

    payment.status      = Payment.STATUS_VERIFIED
    payment.verified_by = admin_user
    payment.verified_at = timezone.now()
    if note:
        payment.admin_note = note
    payment.save()

    order = payment.order
    _advance_order_to_verified(order, changed_by=admin_user, note=note or 'Manual UPI payment approved.')

    return payment


@transaction.atomic
def reject_upi_payment(payment: Payment, admin_user, note: str = '') -> Payment:
    """
    Admin action: reject a manual UPI payment after review.
    Restores stock and cancels the order.
    """
    from orders.services import restore_stock_for_order

    payment.status      = Payment.STATUS_FAILED
    payment.verified_by = admin_user
    payment.verified_at = timezone.now()
    payment.admin_note  = note or 'Payment rejected by admin.'
    payment.save()

    order = payment.order
    if order.status not in (Order.STATUS_CANCELLED, Order.STATUS_REFUNDED):
        old_status = order.status
        order.status = Order.STATUS_CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        OrderStatusHistory.objects.create(
            order=order,
            from_status=old_status,
            to_status=Order.STATUS_CANCELLED,
            note=f'Order cancelled: UPI payment rejected. {note}',
            changed_by=admin_user,
        )
        restore_stock_for_order(order, changed_by=admin_user)

    return payment


# ── Internal helpers ──────────────────────────────────────────────────────────────

def _advance_order_to_verified(order: Order, changed_by=None, note: str = ''):
    """Move an order from any pre-verified status to payment_verified."""
    old_status = order.status
    order.status = Order.STATUS_PAYMENT_VERIFIED
    order.save(update_fields=['status', 'updated_at'])
    OrderStatusHistory.objects.create(
        order=order,
        from_status=old_status,
        to_status=Order.STATUS_PAYMENT_VERIFIED,
        note=note or 'Payment verified.',
        changed_by=changed_by,
    )
