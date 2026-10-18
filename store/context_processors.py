"""
Global template context — cart count and store settings injected into every page.
"""
from .models import StoreSettings


def cart_count(request):
    """Return the number of distinct items currently in the session cart."""
    cart = request.session.get('cart', {})
    count = sum(item.get('quantity', 0) for item in cart.values())
    return {'cart_count': count}


def store_settings(request):
    """Inject the singleton StoreSettings into every template."""
    return {'store_settings': StoreSettings.get()}
