"""
Admin dashboard views — staff-only.
Covers: home stats, orders, products, inventory, payments, earnings, settings.
"""
import csv
import logging
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Sum, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from orders.models import Order, OrderItem, OrderStatusHistory, Shipment
from orders.services import restore_stock_for_order
from payments.models import Payment
from payments.services import approve_upi_payment, reject_upi_payment
from store.models import Category, Product, ProductImage, StockMovement, StoreSettings
from notifications.services import send_order_notifications

logger = logging.getLogger(__name__)


# ── Staff-only decorator ──────────────────────────────────────────────────────────

def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            messages.error(request, 'Access denied.')
            return redirect('store:home')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ── Dashboard home ────────────────────────────────────────────────────────────────

@staff_required
def home(request):
    today       = timezone.localdate()
    month_start = today.replace(day=1)

    orders_qs = Order.objects.all()
    verified  = Payment.objects.filter(status=Payment.STATUS_VERIFIED)

    def _rev(qs):
        return qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    stats = {
        'total_orders':   orders_qs.count(),
        'today_orders':   orders_qs.filter(created_at__date=today).count(),
        'verify_pending': orders_qs.filter(status=Order.STATUS_PAYMENT_VERIFICATION_PENDING).count(),
        'dispatched':     orders_qs.filter(status=Order.STATUS_DISPATCHED).count(),
        'delivered':      orders_qs.filter(status=Order.STATUS_DELIVERED).count(),
        'cancelled':      orders_qs.filter(status=Order.STATUS_CANCELLED).count(),
        'active_products': Product.objects.filter(status=Product.STATUS_ACTIVE).count(),
        'low_stock':       Product.objects.filter(status=Product.STATUS_ACTIVE, stock__gt=0, stock__lte=5).count(),
        'out_of_stock':    Product.objects.filter(status=Product.STATUS_ACTIVE, stock=0).count(),
        'revenue_today':  _rev(verified.filter(verified_at__date=today)),
        'revenue_month':  _rev(verified.filter(verified_at__date__gte=month_start)),
        'revenue_total':  _rev(verified),
    }

    recent_orders = orders_qs.order_by('-created_at')[:10]
    pending_upi   = Payment.objects.filter(
        method=Payment.METHOD_UPI_MANUAL,
        status=Payment.STATUS_VERIFICATION_PENDING,
    ).select_related('order').order_by('created_at')[:8]

    # 7-day revenue chart
    chart_labels, chart_data = [], []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        rev = _rev(verified.filter(verified_at__date=d))
        chart_labels.append(d.strftime('%d %b'))
        chart_data.append(float(rev))

    return render(request, 'dashboard/home.html', {
        'active_nav':    'home',
        'stats':         stats,
        'recent_orders': recent_orders,
        'pending_upi':   pending_upi,
        'chart_labels':  chart_labels,
        'chart_data':    chart_data,
    })


# ── Orders ────────────────────────────────────────────────────────────────────────

@staff_required
def orders(request):
    qs = Order.objects.all().order_by('-created_at')

    search  = request.GET.get('q', '').strip()
    status  = request.GET.get('status', '').strip()
    d_from  = request.GET.get('date_from', '').strip()
    d_to    = request.GET.get('date_to', '').strip()

    if search:
        qs = qs.filter(
            Q(reference__icontains=search) | Q(customer_name__icontains=search) |
            Q(customer_email__icontains=search) | Q(customer_phone__icontains=search)
        )
    if status:
        qs = qs.filter(status=status)
    if d_from:
        qs = qs.filter(created_at__date__gte=d_from)
    if d_to:
        qs = qs.filter(created_at__date__lte=d_to)

    page_obj = Paginator(qs, 25).get_page(request.GET.get('page'))

    return render(request, 'dashboard/orders.html', {
        'active_nav':     'orders',
        'page_obj':       page_obj,
        'status_choices': Order.STATUS_CHOICES,
        'status_filter':  status,
        'search':         search,
        'date_from':      d_from,
        'date_to':        d_to,
    })


@staff_required
def order_detail(request, order_ref):
    order    = get_object_or_404(Order, reference=order_ref.upper())
    payment  = order.payments.order_by('-created_at').first()
    history  = order.history.order_by('created_at')
    shipment, _ = Shipment.objects.get_or_create(order=order)

    return render(request, 'dashboard/order_detail.html', {
        'active_nav':    'orders',
        'order':         order,
        'payment':       payment,
        'history':       history,
        'shipment':      shipment,
        'allowed_next':  Order.VALID_TRANSITIONS.get(order.status, []),
        'status_choices': Order.STATUS_CHOICES,
    })


@staff_required
@require_POST
def update_order_status(request, order_ref):
    order      = get_object_or_404(Order, reference=order_ref.upper())
    new_status = request.POST.get('new_status', '').strip()
    note       = request.POST.get('note', '').strip()

    if not order.can_transition_to(new_status):
        messages.error(request, f'Invalid status transition from "{order.get_status_display()}".')
        return redirect('dashboard:order_detail', order_ref=order.reference)

    with transaction.atomic():
        old = order.status
        order.status = new_status
        if note:
            order.admin_note = note
        order.save(update_fields=['status', 'admin_note', 'updated_at'])

        OrderStatusHistory.objects.create(
            order=order, from_status=old, to_status=new_status,
            note=note or f'Updated by {request.user.get_full_name() or request.user.username}.',
            changed_by=request.user,
        )

        if new_status == Order.STATUS_CANCELLED:
            restore_stock_for_order(order, changed_by=request.user)

        event_map = {
            Order.STATUS_DISPATCHED: 'order_dispatched',
            Order.STATUS_DELIVERED:  'order_delivered',
            Order.STATUS_CANCELLED:  'order_cancelled',
            Order.STATUS_REFUNDED:   'refunded',
        }
        if new_status in event_map:
            try:
                send_order_notifications(order, event_map[new_status])
            except Exception:
                logger.exception('Notification error after status update')

    messages.success(request, f'Order {order.reference} → {order.get_status_display()}.')
    return redirect('dashboard:order_detail', order_ref=order.reference)


@staff_required
@require_POST
def update_shipment(request, order_ref):
    order    = get_object_or_404(Order, reference=order_ref.upper())
    shipment, _ = Shipment.objects.get_or_create(order=order)

    shipment.courier_name = request.POST.get('courier_name', '').strip()
    shipment.awb_number   = request.POST.get('awb_number', '').strip()
    shipment.tracking_url = request.POST.get('tracking_url', '').strip()

    for field, attr in [('dispatch_date', 'dispatch_date'), ('delivery_date', 'delivery_date')]:
        raw = request.POST.get(field, '').strip()
        if raw:
            try:
                setattr(shipment, attr, date.fromisoformat(raw))
            except ValueError:
                pass

    shipment.save()
    messages.success(request, 'Shipment details saved.')
    return redirect('dashboard:order_detail', order_ref=order.reference)


# ── Payments ──────────────────────────────────────────────────────────────────────

@staff_required
def payments(request):
    qs = Payment.objects.select_related('order').order_by('-created_at')

    if request.GET.get('method'):
        qs = qs.filter(method=request.GET['method'])
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET['status'])

    page_obj = Paginator(qs, 25).get_page(request.GET.get('page'))

    return render(request, 'dashboard/payments.html', {
        'active_nav':     'payments',
        'page_obj':       page_obj,
        'method_choices': Payment.METHOD_CHOICES,
        'status_choices': Payment.STATUS_CHOICES,
        'method_filter':  request.GET.get('method', ''),
        'status_filter':  request.GET.get('status', ''),
    })


@staff_required
@require_POST
def verify_upi_payment(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id, method=Payment.METHOD_UPI_MANUAL)
    note    = request.POST.get('note', '').strip()
    action  = request.POST.get('action', '').strip()

    if action == 'approve':
        approve_upi_payment(payment, request.user, note)
        try:
            send_order_notifications(payment.order, 'payment_confirmed')
        except Exception:
            pass
        messages.success(request, f'Payment approved for {payment.order.reference}.')
    elif action == 'reject':
        reject_upi_payment(payment, request.user, note)
        try:
            send_order_notifications(payment.order, 'payment_rejected')
        except Exception:
            pass
        messages.warning(request, f'Payment rejected for {payment.order.reference}.')
    else:
        messages.error(request, 'Invalid action.')

    # Redirect back to where we came from
    referer = request.META.get('HTTP_REFERER', '')
    if 'order_detail' in referer or 'orders/' in referer:
        return redirect('dashboard:order_detail', order_ref=payment.order.reference)
    return redirect('dashboard:payments')


# ── Products ──────────────────────────────────────────────────────────────────────

@staff_required
def products(request):
    qs = Product.objects.select_related('category').order_by('-created_at')

    if request.GET.get('q'):
        q = request.GET['q'].strip()
        qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q))
    if request.GET.get('cat'):
        qs = qs.filter(category_id=request.GET['cat'])
    if request.GET.get('status'):
        qs = qs.filter(status=request.GET['status'])

    page_obj = Paginator(qs, 20).get_page(request.GET.get('page'))

    return render(request, 'dashboard/products.html', {
        'active_nav': 'products',
        'page_obj':   page_obj,
        'categories': Category.objects.filter(is_active=True),
        'search':     request.GET.get('q', ''),
        'cat_id':     request.GET.get('cat', ''),
        'status_filter': request.GET.get('status', ''),
    })


@staff_required
def product_form(request, pk=None):
    product    = get_object_or_404(Product, pk=pk) if pk else None
    categories = Category.objects.filter(is_active=True)
    errors     = {}

    if request.method == 'POST':
        name  = request.POST.get('name', '').strip()
        sku   = request.POST.get('sku', '').strip()
        price = request.POST.get('selling_price', '').strip()

        if not name:  errors['name']  = 'Product name is required.'
        if not sku:   errors['sku']   = 'SKU is required.'
        if not price: errors['selling_price'] = 'Selling price is required.'

        if not errors:
            def _dec(v, default=None):
                try: return Decimal(v) if v else default
                except Exception: return default

            if product is None:
                product = Product()

            product.name           = name
            product.sku            = sku
            product.selling_price  = _dec(price, Decimal('0'))
            product.original_price = _dec(request.POST.get('original_price', ''))
            product.cost_price     = _dec(request.POST.get('cost_price', ''))
            product.description    = request.POST.get('description', '').strip()
            product.stock          = int(request.POST.get('stock') or 0)
            product.low_stock_threshold = int(request.POST.get('low_stock_threshold') or 5)
            product.weight_grams   = int(request.POST.get('weight_grams') or 0)
            product.status         = request.POST.get('status', Product.STATUS_ACTIVE)
            product.is_featured    = 'is_featured'    in request.POST
            product.is_new_arrival = 'is_new_arrival' in request.POST
            product.is_best_seller = 'is_best_seller' in request.POST

            cat_id = request.POST.get('category', '')
            product.category = Category.objects.filter(pk=cat_id).first() if cat_id else None
            product.save()

            img = request.FILES.get('image')
            if img:
                if img.content_type.startswith('image/') and img.size <= 5 * 1024 * 1024:
                    ProductImage.objects.create(
                        product=product, image=img,
                        alt_text=product.name,
                        is_primary=not product.images.exists(),
                    )
                else:
                    messages.warning(request, 'Image skipped — must be an image file under 5 MB.')

            messages.success(request, f'Product "{product.name}" saved.')
            return redirect('dashboard:products')

    return render(request, 'dashboard/product_form.html', {
        'active_nav': 'products',
        'product':    product,
        'categories': categories,
        'errors':     errors,
    })


@staff_required
@require_POST
def delete_product_image(request, image_id):
    img = get_object_or_404(ProductImage, pk=image_id)
    pk  = img.product.pk
    img.delete()
    messages.success(request, 'Image deleted.')
    return redirect('dashboard:product_edit', pk=pk)


# ── Inventory ─────────────────────────────────────────────────────────────────────

@staff_required
def inventory(request):
    all_active = Product.objects.filter(status=Product.STATUS_ACTIVE).select_related('category').order_by('stock')
    page_obj   = Paginator(all_active, 25).get_page(request.GET.get('page'))
    low_stock  = all_active.filter(stock__gt=0, stock__lte=5)
    out_stock  = all_active.filter(stock=0)
    movements  = StockMovement.objects.select_related('product', 'performed_by').order_by('-created_at')[:30]

    return render(request, 'dashboard/inventory.html', {
        'active_nav': 'inventory',
        'page_obj':   page_obj,
        'low_stock':  low_stock,
        'out_stock':  out_stock,
        'movements':  movements,
    })


@staff_required
@require_POST
def adjust_stock(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    try:
        qty_change = int(request.POST.get('qty_change', 0))
    except ValueError:
        messages.error(request, 'Invalid quantity.')
        return redirect('dashboard:inventory')

    note    = request.POST.get('note', '').strip() or 'Manual adjustment'
    new_qty = max(0, product.stock + qty_change)

    with transaction.atomic():
        product.stock = new_qty
        product.save(update_fields=['stock', 'updated_at'])
        StockMovement.objects.create(
            product=product, quantity_change=qty_change,
            reason=StockMovement.REASON_ADJUSTMENT,
            note=note, performed_by=request.user,
        )

    messages.success(request, f'"{product.name}" stock updated to {new_qty}.')
    return redirect('dashboard:inventory')


# ── Earnings ──────────────────────────────────────────────────────────────────────

@staff_required
def earnings(request):
    today       = timezone.localdate()
    week_start  = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start  = today.replace(month=1, day=1)

    verified = Payment.objects.filter(status=Payment.STATUS_VERIFIED)

    def _rev(qs):
        return qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    revenue = {
        'today': _rev(verified.filter(verified_at__date=today)),
        'week':  _rev(verified.filter(verified_at__date__gte=week_start)),
        'month': _rev(verified.filter(verified_at__date__gte=month_start)),
        'year':  _rev(verified.filter(verified_at__date__gte=year_start)),
        'total': _rev(verified),
    }

    refund_total = Order.objects.filter(
        status=Order.STATUS_REFUNDED
    ).aggregate(t=Sum('total_amount'))['t'] or Decimal('0')

    top_products = (
        OrderItem.objects
        .filter(order__status__in=[
            Order.STATUS_PAYMENT_VERIFIED, Order.STATUS_PROCESSING,
            Order.STATUS_PACKED, Order.STATUS_DISPATCHED, Order.STATUS_DELIVERED,
        ])
        .values('product_name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:10]
    )

    status_counts = (
        Order.objects.values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )

    paid_orders = Order.objects.filter(
        status__in=[Order.STATUS_PAYMENT_VERIFIED, Order.STATUS_DELIVERED]
    )
    order_count = paid_orders.count()
    total_paid  = paid_orders.aggregate(t=Sum('total_amount'))['t'] or Decimal('0')
    avg_value   = (total_paid / order_count) if order_count else Decimal('0')

    # Monthly chart — last 6 months
    chart_labels, chart_data = [], []
    for i in range(5, -1, -1):
        first = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        if i == 0:
            last = today
        else:
            import calendar
            _, last_day = calendar.monthrange(first.year, first.month)
            last = first.replace(day=last_day)
        rev = _rev(verified.filter(verified_at__date__gte=first, verified_at__date__lte=last))
        chart_labels.append(first.strftime('%b %Y'))
        chart_data.append(float(rev))

    return render(request, 'dashboard/earnings.html', {
        'active_nav':    'earnings',
        'revenue':       revenue,
        'refund_total':  refund_total,
        'top_products':  top_products,
        'status_counts': status_counts,
        'order_count':   order_count,
        'avg_value':     avg_value,
        'chart_labels':  chart_labels,
        'chart_data':    chart_data,
    })


@staff_required
def export_orders_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="vayunandhan_orders.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Order Ref', 'Date', 'Customer Name', 'Email', 'Phone',
        'City', 'State', 'Pincode', 'Subtotal', 'Delivery',
        'Discount', 'Total', 'Payment Method', 'Payment Status',
        'Order Status', 'Courier', 'AWB',
    ])
    for o in Order.objects.select_related().order_by('-created_at'):
        p = o.payments.order_by('-created_at').first()
        s = getattr(o, 'shipment', None)
        writer.writerow([
            o.reference, o.created_at.strftime('%Y-%m-%d %H:%M'),
            o.customer_name, o.customer_email, o.customer_phone,
            o.city, o.state, o.pincode,
            o.subtotal, o.delivery_charge, o.discount_amount, o.total_amount,
            p.get_method_display() if p else '',
            p.get_status_display() if p else '',
            o.get_status_display(),
            s.courier_name if s else '',
            s.awb_number   if s else '',
        ])
    return response


# ── Store settings ────────────────────────────────────────────────────────────────

@staff_required
def settings_view(request):
    store = StoreSettings.get()

    if request.method == 'POST':
        store.store_name      = request.POST.get('store_name', '').strip() or store.store_name
        store.tagline         = request.POST.get('tagline', '').strip()
        store.email           = request.POST.get('email', '').strip()
        store.phone           = request.POST.get('phone', '').strip()
        store.whatsapp_number = request.POST.get('whatsapp_number', '').strip()
        store.instagram_url   = request.POST.get('instagram_url', '').strip()
        store.facebook_url    = request.POST.get('facebook_url', '').strip()
        store.address         = request.POST.get('address', '').strip()
        store.upi_id          = request.POST.get('upi_id', '').strip()
        store.upi_display_name = request.POST.get('upi_display_name', '').strip()
        store.upi_payment_instructions = request.POST.get('upi_payment_instructions', '').strip()

        try:
            store.delivery_charge     = Decimal(request.POST.get('delivery_charge') or '0')
            store.free_delivery_above = Decimal(request.POST.get('free_delivery_above') or '0')
        except Exception:
            pass

        store.notify_order_created     = 'notify_order_created'     in request.POST
        store.notify_payment_confirmed = 'notify_payment_confirmed' in request.POST
        store.notify_order_dispatched  = 'notify_order_dispatched'  in request.POST

        for field_name in ('logo', 'upi_qr_code'):
            f = request.FILES.get(field_name)
            if f and f.content_type.startswith('image/') and f.size <= 5 * 1024 * 1024:
                setattr(store, field_name, f)

        store.save()
        messages.success(request, 'Settings saved successfully.')
        return redirect('dashboard:settings')

    return render(request, 'dashboard/settings.html', {
        'active_nav': 'settings',
        'store':      store,
    })
