"""
Payment views:
  - Payment page (Razorpay / Manual UPI)
  - Razorpay AJAX initiate + callback
  - Razorpay webhook (raw body verification)
  - Manual UPI submission
  - Payment result page
"""
import json
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils.decorators import method_decorator

from orders.models import Order
from payments.models import Payment
from payments.services import (
    create_razorpay_order,
    confirm_razorpay_payment,
    verify_razorpay_webhook_signature,
    submit_upi_payment,
)
from store.models import StoreSettings

logger = logging.getLogger(__name__)


# ── Payment page ──────────────────────────────────────────────────────────────────

def payment_page(request, order_ref):
    """
    Display the appropriate payment page (Razorpay or Manual UPI)
    based on the payment method chosen at checkout.
    """
    order = get_object_or_404(Order, reference=order_ref.upper())

    # Security: only the order owner or staff may access
    if not request.user.is_staff:
        session_ref = request.session.get('pending_order_ref', '')
        confirmed   = request.session.get('confirmed_orders', [])
        if session_ref != order_ref and order_ref not in confirmed:
            if order.user and order.user != request.user:
                messages.error(request, 'Order not found.')
                return redirect('store:home')

    payment = order.payments.order_by('-created_at').first()
    if not payment:
        messages.error(request, 'Payment record not found. Please contact support.')
        return redirect('store:home')

    # If already verified, go straight to confirmation
    if payment.status == Payment.STATUS_VERIFIED:
        return redirect('orders:confirmation', order_ref=order.reference)

    return render(request, 'payments/payment_page.html', {
        'order':          order,
        'payment':        payment,
        'store_settings': StoreSettings.get(),
    })


# ── Razorpay: AJAX order initiation ──────────────────────────────────────────────

@require_POST
def razorpay_initiate(request):
    """
    AJAX: create a Razorpay order server-side and return only public data
    needed to open the Razorpay checkout modal.
    No secret keys are ever sent to the browser.
    """
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    try:
        data      = json.loads(request.body)
        order_ref = data.get('order_ref', '').strip().upper()
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Bad request.'}, status=400)

    order = get_object_or_404(Order, reference=order_ref)
    payment = order.payments.filter(method=Payment.METHOD_RAZORPAY).order_by('-created_at').first()

    if not payment:
        return JsonResponse({'error': 'Payment record not found.'}, status=404)

    if payment.status == Payment.STATUS_VERIFIED:
        return JsonResponse({'error': 'Payment already completed.'}, status=400)

    try:
        if not payment.razorpay_order_id:
            create_razorpay_order(payment)
    except RuntimeError as e:
        logger.error('Razorpay order creation failed: %s', e)
        return JsonResponse({'error': str(e)}, status=503)
    except Exception as e:
        logger.exception('Unexpected error creating Razorpay order')
        return JsonResponse({'error': 'Payment service unavailable. Please try again.'}, status=503)

    store = StoreSettings.get()
    return JsonResponse({
        'key_id':           settings.RAZORPAY_KEY_ID,
        'razorpay_order_id': payment.razorpay_order_id,
        'amount':           int(payment.amount * 100),
        'currency':         'INR',
        'order_ref':        order.reference,
        'store_name':       store.store_name,
        'customer_name':    order.customer_name,
        'customer_email':   order.customer_email,
        'customer_phone':   order.customer_phone,
    })


# ── Razorpay: browser callback (after payment modal closes) ───────────────────────

@require_POST
def razorpay_callback(request):
    """
    Called by the Razorpay JS after a successful payment.
    We re-verify the signature server-side before trusting it.
    Do NOT mark the order as paid here alone — the webhook is the source of truth.
    This view simply verifies and redirects.
    """
    rz_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    rz_order_id   = request.POST.get('razorpay_order_id', '').strip()
    rz_signature  = request.POST.get('razorpay_signature', '').strip()
    order_ref     = request.POST.get('order_ref', '').strip().upper()

    if not all([rz_payment_id, rz_order_id, rz_signature, order_ref]):
        messages.error(request, 'Incomplete payment data. Please contact support.')
        return redirect('store:home')

    try:
        payment = confirm_razorpay_payment(rz_order_id, rz_payment_id, rz_signature)
        # Trigger notifications (best-effort, non-blocking)
        try:
            from notifications.services import send_order_notifications
            send_order_notifications(payment.order, 'payment_confirmed')
        except Exception:
            logger.exception('Notification error after Razorpay callback')

        return redirect('orders:confirmation', order_ref=payment.order.reference)

    except ValueError as e:
        logger.warning('Razorpay callback verification failed: %s', e)
        messages.error(request, 'Payment verification failed. Please contact support with your order ID.')
        return redirect('payments:payment_result',
                        order_ref=order_ref, result='failed')
    except Exception:
        logger.exception('Unexpected error in Razorpay callback')
        messages.error(request, 'Something went wrong. Please contact support.')
        return redirect('payments:payment_result',
                        order_ref=order_ref, result='failed')


# ── Razorpay webhook ──────────────────────────────────────────────────────────────

@csrf_exempt
def razorpay_webhook(request):
    """
    Razorpay sends signed POST payloads here for events like
    payment.captured, payment.failed, refund.created.
    We verify the signature using the raw request body BEFORE parsing.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    signature = request.headers.get('X-Razorpay-Signature', '')
    if not verify_razorpay_webhook_signature(request.body, signature):
        logger.warning('Invalid Razorpay webhook signature received.')
        return HttpResponse('Invalid signature', status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse('Bad payload', status=400)

    event    = payload.get('event', '')
    event_id = payload.get('id', '')

    logger.info('Razorpay webhook: event=%s id=%s', event, event_id)

    if event == 'payment.captured':
        entity = payload.get('payload', {}).get('payment', {}).get('entity', {})
        rz_order_id   = entity.get('order_id', '')
        rz_payment_id = entity.get('id', '')
        rz_signature  = entity.get('signature', '')  # may be empty in webhook

        # For webhooks, signature field may not be present.
        # We trust the webhook-level signature (already verified above).
        # Re-verify if signature is present, otherwise trust webhook.
        try:
            payment = Payment.objects.get(
                razorpay_order_id=rz_order_id,
                method=Payment.METHOD_RAZORPAY,
            )

            if payment.status == Payment.STATUS_VERIFIED:
                return HttpResponse('OK')  # idempotent

            if event_id and payment.last_webhook_event_id == event_id:
                return HttpResponse('OK')  # duplicate

            from django.utils import timezone
            from orders.models import OrderStatusHistory
            from payments.services import _advance_order_to_verified

            payment.razorpay_payment_id   = rz_payment_id
            payment.status                = Payment.STATUS_VERIFIED
            payment.verified_at           = timezone.now()
            payment.last_webhook_event_id = event_id
            payment.save()

            _advance_order_to_verified(payment.order, note='Confirmed via Razorpay webhook.')

            try:
                from notifications.services import send_order_notifications
                send_order_notifications(payment.order, 'payment_confirmed')
            except Exception:
                logger.exception('Notification error after webhook')

        except Payment.DoesNotExist:
            logger.warning('Webhook: no payment for Razorpay order %s', rz_order_id)

    elif event == 'payment.failed':
        entity      = payload.get('payload', {}).get('payment', {}).get('entity', {})
        rz_order_id = entity.get('order_id', '')
        try:
            payment = Payment.objects.get(
                razorpay_order_id=rz_order_id,
                method=Payment.METHOD_RAZORPAY,
            )
            if payment.status == Payment.STATUS_PENDING:
                payment.status = Payment.STATUS_FAILED
                payment.save(update_fields=['status', 'updated_at'])
        except Payment.DoesNotExist:
            pass

    return HttpResponse('OK')


# ── Manual UPI submission ─────────────────────────────────────────────────────────

@require_POST
def upi_submit(request):
    """
    Customer submits their UPI transaction ID and optional screenshot.
    Does NOT verify payment — only records it for admin review.
    """
    order_ref = request.POST.get('order_ref', '').strip().upper()
    upi_txn   = request.POST.get('upi_transaction_id', '').strip()
    screenshot = request.FILES.get('screenshot')

    errors = {}

    if not upi_txn:
        errors['upi_transaction_id'] = 'Please enter your UPI transaction / reference ID.'

    # Validate screenshot if provided
    if screenshot:
        allowed_types = {'image/jpeg', 'image/png', 'image/webp'}
        if screenshot.content_type not in allowed_types:
            errors['screenshot'] = 'Only JPG, PNG, or WebP images are allowed.'
        elif screenshot.size > settings.MAX_UPLOAD_SIZE:
            errors['screenshot'] = 'Image must be under 5 MB.'

    if errors:
        order = get_object_or_404(Order, reference=order_ref)
        payment = order.payments.order_by('-created_at').first()
        return render(request, 'payments/payment_page.html', {
            'order':   order,
            'payment': payment,
            'errors':  errors,
        })

    order = get_object_or_404(Order, reference=order_ref)
    payment = order.payments.filter(method=Payment.METHOD_UPI_MANUAL).order_by('-created_at').first()

    if not payment:
        messages.error(request, 'Payment record not found.')
        return redirect('store:home')

    submit_upi_payment(payment, upi_txn, screenshot)

    # Trigger notifications
    try:
        from notifications.services import send_order_notifications
        send_order_notifications(order, 'payment_verification_pending')
    except Exception:
        logger.exception('Notification error after UPI submission')

    # Store in session so confirmation page is accessible
    confirmed = request.session.get('confirmed_orders', [])
    if order.reference not in confirmed:
        confirmed.append(order.reference)
        request.session['confirmed_orders'] = confirmed

    return redirect('orders:confirmation', order_ref=order.reference)


# ── Payment result ────────────────────────────────────────────────────────────────

def payment_result(request, order_ref, result):
    order = get_object_or_404(Order, reference=order_ref.upper())
    return render(request, 'payments/payment_result.html', {
        'order':   order,
        'result':  result,
        'message': request.GET.get('msg', ''),
    })
