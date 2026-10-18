"""
Order creation service — the single authoritative place where an Order
and its Items are persisted, stock is reserved, and the cart is cleared.

All financial values are computed server-side; nothing from the browser
is trusted for pricing.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from store.models import Product, StockMovement
from store.services import build_cart_summary, calculate_delivery_charge
from orders.models import Order, OrderItem, OrderStatusHistory
from payments.models import Payment


class CartValidationError(Exception):
    """Raised when the cart cannot be converted to an order."""
    pass


@transaction.atomic
def create_order_from_cart(cart: dict, form_data: dict, user=None) -> tuple:
    """
    Validate the cart, create an Order + OrderItems, reserve stock,
    and create a pending Payment record.

    Returns (order, payment).
    Raises CartValidationError with a human-readable message on failure.
    """
    summary = build_cart_summary(cart)

    if not summary['items']:
        raise CartValidationError('Your cart is empty or all products are unavailable.')

    # ── Re-validate every product with SELECT FOR UPDATE to prevent overselling ──
    validated_items = []
    for entry in summary['items']:
        product = (
            Product.objects
            .select_for_update()
            .get(pk=entry['product'].pk)
        )
        qty = entry['quantity']

        if product.status != Product.STATUS_ACTIVE:
            raise CartValidationError(
                f'"{product.name}" is no longer available.'
            )
        if product.stock < qty:
            available = product.stock
            if available == 0:
                raise CartValidationError(
                    f'"{product.name}" is out of stock.'
                )
            raise CartValidationError(
                f'Only {available} unit(s) of "{product.name}" are available.'
            )
        validated_items.append((product, qty, entry['subtotal']))

    # ── Build financials ─────────────────────────────────────────────────────────
    subtotal  = sum(s for _, _, s in validated_items)
    delivery  = calculate_delivery_charge(subtotal)
    discount  = summary['discount']
    total     = max(subtotal + delivery - discount, Decimal('0.00'))

    payment_method = form_data.get('payment_method', 'razorpay')

    # ── Create Order ─────────────────────────────────────────────────────────────
    order = Order.objects.create(
        user=user if (user and user.is_authenticated) else None,
        customer_name=form_data['customer_name'],
        customer_email=form_data['customer_email'],
        customer_phone=form_data['customer_phone'],
        address_line1=form_data['address_line1'],
        address_line2=form_data.get('address_line2', ''),
        city=form_data['city'],
        state=form_data['state'],
        pincode=form_data['pincode'],
        delivery_instructions=form_data.get('delivery_instructions', ''),
        subtotal=subtotal,
        delivery_charge=delivery,
        discount_amount=discount,
        total_amount=total,
        status=Order.STATUS_PLACED,
    )

    # ── Create OrderItems + deduct stock ─────────────────────────────────────────
    for product, qty, item_sub in validated_items:
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            product_sku=product.sku,
            unit_price=product.selling_price,
            original_price=product.original_price,
            quantity=qty,
        )
        # Deduct stock immediately (reserved for this order)
        product.stock -= qty
        product.save(update_fields=['stock', 'updated_at'])

        StockMovement.objects.create(
            product=product,
            quantity_change=-qty,
            reason=StockMovement.REASON_SALE,
            order_reference=order.reference,
            note=f'Order {order.reference}',
        )

    # ── Status history ───────────────────────────────────────────────────────────
    OrderStatusHistory.objects.create(
        order=order,
        from_status='',
        to_status=Order.STATUS_PLACED,
        note='Order created.',
    )

    # ── Create pending Payment record ────────────────────────────────────────────
    payment = Payment.objects.create(
        order=order,
        method=payment_method,
        amount=total,
        currency='INR',
        status=Payment.STATUS_PENDING,
    )

    return order, payment


def restore_stock_for_order(order: Order, changed_by=None):
    """
    Restore stock for all items in a cancelled/refunded order.
    Safe to call multiple times — checks StockMovement for duplicates.
    """
    with transaction.atomic():
        for item in order.items.all():
            if item.product is None:
                continue
            product = Product.objects.select_for_update().get(pk=item.product.pk)

            # Prevent double-restore
            already_restored = StockMovement.objects.filter(
                product=product,
                order_reference=order.reference,
                reason=StockMovement.REASON_RETURN,
            ).exists()
            if already_restored:
                continue

            product.stock += item.quantity
            product.save(update_fields=['stock', 'updated_at'])

            StockMovement.objects.create(
                product=product,
                quantity_change=item.quantity,
                reason=StockMovement.REASON_RETURN,
                order_reference=order.reference,
                note=f'Stock restored for {order.status} order {order.reference}',
                performed_by=changed_by,
            )


def get_cart_items_with_meta(cart: dict) -> list:
    """Return enriched item dicts for template rendering (cart page)."""
    summary = build_cart_summary(cart)
    return summary['items']
