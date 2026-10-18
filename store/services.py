"""
Store-level service helpers: delivery charge calculation.
"""
from decimal import Decimal
from .models import StoreSettings


def calculate_delivery_charge(subtotal: Decimal) -> Decimal:
    """
    Return the delivery charge for a given order subtotal.
    Rules are driven by StoreSettings so no code change is needed.
    """
    settings = StoreSettings.get()
    threshold = settings.free_delivery_above or Decimal('0')
    if threshold > 0 and subtotal >= threshold:
        return Decimal('0.00')
    return settings.delivery_charge or Decimal('0.00')


def build_cart_summary(cart: dict) -> dict:
    """
    Given the raw session cart dict, fetch live product prices and
    return a complete summary dict.  Never trusts prices stored in session.
    """
    from store.models import Product

    items = []
    subtotal = Decimal('0.00')
    discount = Decimal('0.00')

    for product_id_str, entry in cart.items():
        try:
            product = Product.objects.get(
                pk=int(product_id_str),
                status=Product.STATUS_ACTIVE
            )
        except Product.DoesNotExist:
            continue

        qty = int(entry.get('quantity', 1))
        qty = max(1, min(qty, product.stock))

        item_subtotal = product.selling_price * qty
        if product.original_price and product.original_price > product.selling_price:
            discount += (product.original_price - product.selling_price) * qty

        subtotal += item_subtotal
        items.append({
            'id': product_id_str,
            'product': product,
            'quantity': qty,
            'subtotal': item_subtotal,
        })

    delivery = calculate_delivery_charge(subtotal)
    total = subtotal + delivery - discount
    settings = StoreSettings.get()
    free_threshold = settings.free_delivery_above or Decimal('0')

    return {
        'items': items,
        'subtotal': subtotal,
        'delivery': delivery,
        'discount': discount,
        'total': max(total, Decimal('0.00')),
        'free_delivery_remaining': max(free_threshold - subtotal, Decimal('0.00')),
    }
