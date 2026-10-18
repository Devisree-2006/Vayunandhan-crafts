"""
Order views: cart, checkout, confirmation, tracking, my orders.
"""
import json
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from store.models import Product
from store.services import build_cart_summary
from .forms import CheckoutForm
from .models import Order, OrderStatusHistory
from .services import create_order_from_cart, CartValidationError


# ── Cart helpers ──────────────────────────────────────────────────────────────────

def _get_cart(request) -> dict:
    return request.session.get('cart', {})


def _save_cart(request, cart: dict):
    request.session['cart'] = cart
    request.session.modified = True


# ── Views ─────────────────────────────────────────────────────────────────────────

def cart(request):
    raw_cart = _get_cart(request)
    summary  = build_cart_summary(raw_cart)
    return render(request, 'orders/cart.html', {
        'cart_items': summary['items'],
        'cart_count': sum(i['quantity'] for i in summary['items']),
        'summary': summary,
    })


@require_POST
def add_to_cart(request, product_id):
    product = get_object_or_404(Product, pk=product_id, status=Product.STATUS_ACTIVE)

    try:
        qty = int(request.POST.get('quantity', 1))
        if qty < 1:
            qty = 1
    except (ValueError, TypeError):
        qty = 1

    # Server-side stock check
    if product.stock < 1:
        msg = f'"{product.name}" is out of stock.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': msg}, status=400)
        messages.error(request, msg)
        return redirect(product.get_absolute_url())

    cart = _get_cart(request)
    key  = str(product.pk)

    current_qty = cart.get(key, {}).get('quantity', 0)
    new_qty = current_qty + qty

    if new_qty > product.stock:
        new_qty = product.stock
        msg = f'Only {product.stock} unit(s) of "{product.name}" are available.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': msg}, status=400)
        messages.warning(request, msg)

    cart[key] = {'quantity': new_qty}
    _save_cart(request, cart)

    total_count = sum(v.get('quantity', 0) for v in cart.values())

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'message': f'"{product.name}" added to cart!',
            'cart_count': total_count,
        })

    messages.success(request, f'"{product.name}" added to your cart! 🛒')
    return redirect(product.get_absolute_url())


@require_POST
def update_cart(request):
    """AJAX endpoint: increase / decrease / remove a cart item."""
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({'error': 'Invalid request.'}, status=400)

    try:
        data    = json.loads(request.body)
        item_id = str(data.get('item_id', ''))
        action  = data.get('action', '')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Bad request.'}, status=400)

    cart = _get_cart(request)

    if item_id not in cart:
        return JsonResponse({'error': 'Item not in cart.'}, status=404)

    if action == 'remove':
        del cart[item_id]
    elif action in ('increase', 'decrease'):
        try:
            product = Product.objects.get(pk=int(item_id), status=Product.STATUS_ACTIVE)
        except Product.DoesNotExist:
            del cart[item_id]
            _save_cart(request, cart)
            return JsonResponse({'item_id': item_id, 'quantity': 0,
                                  'cart_count': sum(v.get('quantity',0) for v in cart.values()),
                                  'summary': _summary_payload(cart)})

        qty = cart[item_id].get('quantity', 1)
        if action == 'increase':
            if qty >= product.stock:
                return JsonResponse({'error': f'Maximum {product.stock} unit(s) available.'}, status=400)
            qty += 1
        else:
            qty -= 1
            if qty <= 0:
                del cart[item_id]
                _save_cart(request, cart)
                total = sum(v.get('quantity',0) for v in cart.values())
                return JsonResponse({'item_id': item_id, 'quantity': 0, 'subtotal': '0.00',
                                      'cart_count': total, 'summary': _summary_payload(cart)})
        cart[item_id]['quantity'] = qty
    else:
        return JsonResponse({'error': 'Unknown action.'}, status=400)

    _save_cart(request, cart)

    summary  = build_cart_summary(cart)
    item_sub = Decimal('0.00')
    for entry in summary['items']:
        if str(entry['product'].pk) == item_id:
            item_sub = entry['subtotal']
            break

    total_count = sum(v.get('quantity', 0) for v in cart.values())
    return JsonResponse({
        'item_id': item_id,
        'quantity': cart.get(item_id, {}).get('quantity', 0),
        'subtotal': str(item_sub),
        'cart_count': total_count,
        'summary': _summary_payload(cart),
    })


def _summary_payload(cart: dict) -> dict:
    s = build_cart_summary(cart)
    return {
        'subtotal': str(s['subtotal']),
        'delivery': str(s['delivery']),
        'discount': str(s['discount']),
        'total':    str(s['total']),
    }


def checkout(request):
    cart = _get_cart(request)
    summary = build_cart_summary(cart)

    if not summary['items']:
        messages.warning(request, 'Your cart is empty. Add some products first!')
        return redirect('orders:cart')

    errors    = {}
    form_data = {}

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            try:
                order, payment = create_order_from_cart(
                    cart=cart,
                    form_data=form.cleaned_data,
                    user=request.user,
                )
                # Clear the cart
                request.session['cart'] = {}
                request.session.modified = True

                # Store order ref in session for payment page
                request.session['pending_order_ref'] = order.reference

                return redirect('payments:payment_page', order_ref=order.reference)

            except CartValidationError as e:
                messages.error(request, str(e))
                # Refresh summary after potential stock changes
                summary = build_cart_summary(_get_cart(request))
        else:
            errors    = {f: e[0] for f, e in form.errors.items()}
            form_data = request.POST.dict()

    # Pre-fill from logged-in user
    if request.user.is_authenticated and not form_data:
        form_data = {
            'customer_name':  request.user.get_full_name() or request.user.username,
            'customer_email': request.user.email,
            'customer_phone': getattr(request.user, 'profile', None) and
                              request.user.profile.phone or '',
        }

    return render(request, 'orders/checkout.html', {
        'cart_items': summary['items'],
        'summary':    summary,
        'errors':     errors,
        'form_data':  form_data,
    })


def order_confirmation(request, order_ref):
    order = get_object_or_404(Order, reference=order_ref)

    # Security: only the owner or staff can view
    if not request.user.is_staff:
        if order.user and order.user != request.user:
            messages.error(request, 'Order not found.')
            return redirect('store:home')
        # Guest access: check session
        if not order.user and request.session.get('pending_order_ref') != order_ref:
            # Allow if email matches a session key (set during checkout)
            allowed_refs = request.session.get('confirmed_orders', [])
            if order_ref not in allowed_refs:
                messages.error(request, 'Order not found.')
                return redirect('store:home')

    # Mark as confirmed in session for guest re-access
    confirmed = request.session.get('confirmed_orders', [])
    if order_ref not in confirmed:
        confirmed.append(order_ref)
        request.session['confirmed_orders'] = confirmed

    payment = order.payments.order_by('-created_at').first()

    return render(request, 'orders/order_confirmation.html', {
        'order': order,
        'payment': payment,
    })


def track_order(request):
    query_ref   = request.GET.get('ref', '').strip().upper()
    query_email = request.GET.get('email', '').strip().lower()
    order       = None
    track_error = None
    timeline_steps = []

    if query_ref and query_email:
        try:
            order = Order.objects.get(
                reference=query_ref,
                customer_email__iexact=query_email,
            )
            timeline_steps = _build_timeline(order)
        except Order.DoesNotExist:
            track_error = (
                'No order found with that reference and email combination. '
                'Please check and try again.'
            )

    return render(request, 'orders/track.html', {
        'order': order,
        'query_ref': query_ref,
        'query_email': query_email,
        'track_error': track_error,
        'timeline_steps': timeline_steps,
    })


def _build_timeline(order: Order) -> list:
    """Map order status to a visual timeline list."""
    STEPS = [
        (Order.STATUS_PLACED,                       'Order Placed'),
        (Order.STATUS_PAYMENT_VERIFICATION_PENDING, 'Payment Verification'),
        (Order.STATUS_PAYMENT_VERIFIED,             'Payment Confirmed'),
        (Order.STATUS_PROCESSING,                   'Processing'),
        (Order.STATUS_PACKED,                       'Packed'),
        (Order.STATUS_DISPATCHED,                   'Dispatched'),
        (Order.STATUS_OUT_FOR_DELIVERY,             'Out for Delivery'),
        (Order.STATUS_DELIVERED,                    'Delivered'),
    ]

    # Build a map of status → timestamp from history
    history_map = {}
    for h in order.history.all():
        history_map[h.to_status] = h.created_at

    STATUS_ORDER = [s for s, _ in STEPS]
    try:
        current_idx = STATUS_ORDER.index(order.status)
    except ValueError:
        current_idx = -1

    steps = []
    for i, (status, label) in enumerate(STEPS):
        done   = i < current_idx
        active = i == current_idx
        ts     = history_map.get(status)
        steps.append({
            'status': status,
            'label':  label,
            'done':   done,
            'active': active,
            'date':   ts.strftime('%d %b %Y, %I:%M %p') if ts else None,
        })
    return steps


@login_required
def my_orders(request):
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'orders/my_orders.html', {'orders': orders})
