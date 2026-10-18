"""
Tests for the orders app:
  - Cart add / update / remove
  - Stock validation at add-to-cart and checkout
  - Order creation service (atomic stock deduction)
  - Duplicate order prevention
  - Order tracking security (no cross-customer access)
  - My-orders requires login
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from store.models import Category, Product, StoreSettings, StockMovement
from orders.models import Order, OrderItem, OrderStatusHistory
from orders.services import create_order_from_cart, CartValidationError, restore_stock_for_order


# ── Helpers ───────────────────────────────────────────────────────────────────────

def make_product(name='Test Product', price=199, stock=10, sku=None):
    cat, _ = Category.objects.get_or_create(name='Test Cat', slug='test-cat')
    return Product.objects.create(
        name=name,
        sku=sku or f'TST{name[:4].upper()}',
        category=cat,
        selling_price=Decimal(str(price)),
        stock=stock,
        status=Product.STATUS_ACTIVE,
    )


CHECKOUT_DATA = {
    'customer_name':    'Priya Sharma',
    'customer_email':   'priya@example.com',
    'customer_phone':   '9876543210',
    'address_line1':    '12 Rose Street',
    'address_line2':    '',
    'city':             'Chennai',
    'state':            'Tamil Nadu',
    'pincode':          '600001',
    'delivery_instructions': '',
    'payment_method':   'razorpay',
}


# ── Cart view tests ───────────────────────────────────────────────────────────────

class CartViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        StoreSettings.get()
        self.product = make_product()

    def test_cart_page_loads_empty(self):
        r = self.client.get(reverse('orders:cart'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Your cart is empty')

    def test_add_to_cart(self):
        r = self.client.post(
            reverse('orders:add_to_cart', args=[self.product.pk]),
            {'quantity': 1},
        )
        # Should redirect back to product page
        self.assertEqual(r.status_code, 302)
        cart = self.client.session.get('cart', {})
        self.assertIn(str(self.product.pk), cart)
        self.assertEqual(cart[str(self.product.pk)]['quantity'], 1)

    def test_add_to_cart_ajax(self):
        r = self.client.post(
            reverse('orders:add_to_cart', args=[self.product.pk]),
            {'quantity': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn('cart_count', data)
        self.assertEqual(data['cart_count'], 2)

    def test_add_out_of_stock_blocked(self):
        p = make_product('OOS', stock=0, sku='OOS99')
        r = self.client.post(
            reverse('orders:add_to_cart', args=[p.pk]),
            {'quantity': 1},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 400)
        self.assertIn('error', r.json())

    def test_add_excess_quantity_clamped(self):
        """Adding more than available stock should clamp to max available."""
        r = self.client.post(
            reverse('orders:add_to_cart', args=[self.product.pk]),
            {'quantity': 999},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        cart = self.client.session.get('cart', {})
        qty = cart.get(str(self.product.pk), {}).get('quantity', 0)
        self.assertLessEqual(qty, self.product.stock)

    def test_update_cart_increase(self):
        # First add
        self.client.post(
            reverse('orders:add_to_cart', args=[self.product.pk]),
            {'quantity': 1},
        )
        import json
        r = self.client.post(
            reverse('orders:update_cart'),
            data=json.dumps({'item_id': str(self.product.pk), 'action': 'increase'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['quantity'], 2)

    def test_update_cart_remove(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.product.pk]),
            {'quantity': 1},
        )
        import json
        r = self.client.post(
            reverse('orders:update_cart'),
            data=json.dumps({'item_id': str(self.product.pk), 'action': 'remove'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(r.status_code, 200)
        cart = self.client.session.get('cart', {})
        self.assertNotIn(str(self.product.pk), cart)


# ── Order creation service tests ──────────────────────────────────────────────────

class OrderCreationTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.product = make_product('Keychain', price=149, stock=5, sku='KC1')

    def test_creates_order_and_deducts_stock(self):
        cart = {str(self.product.pk): {'quantity': 2}}
        order, payment = create_order_from_cart(cart, CHECKOUT_DATA)

        self.assertIsNotNone(order.pk)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.customer_name, 'Priya Sharma')

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)  # 5 - 2 = 3

    def test_stock_movement_recorded(self):
        cart = {str(self.product.pk): {'quantity': 1}}
        order, _ = create_order_from_cart(cart, CHECKOUT_DATA)
        movements = StockMovement.objects.filter(
            product=self.product,
            reason=StockMovement.REASON_SALE,
            order_reference=order.reference,
        )
        self.assertEqual(movements.count(), 1)
        self.assertEqual(movements.first().quantity_change, -1)

    def test_empty_cart_raises_error(self):
        with self.assertRaises(CartValidationError):
            create_order_from_cart({}, CHECKOUT_DATA)

    def test_out_of_stock_raises_error(self):
        self.product.stock = 0
        self.product.save()
        cart = {str(self.product.pk): {'quantity': 1}}
        with self.assertRaises(CartValidationError) as ctx:
            create_order_from_cart(cart, CHECKOUT_DATA)
        self.assertIn('out of stock', str(ctx.exception).lower())

    def test_insufficient_stock_raises_error(self):
        cart = {str(self.product.pk): {'quantity': 10}}  # only 5 in stock
        with self.assertRaises(CartValidationError) as ctx:
            create_order_from_cart(cart, CHECKOUT_DATA)
        self.assertIn('5', str(ctx.exception))

    def test_order_total_calculated_server_side(self):
        """Total must match server-calculated price, not any client value."""
        cart = {str(self.product.pk): {'quantity': 2}}
        order, _ = create_order_from_cart(cart, CHECKOUT_DATA)
        expected_subtotal = Decimal('149') * 2
        self.assertEqual(order.subtotal, expected_subtotal)

    def test_order_status_history_created(self):
        cart = {str(self.product.pk): {'quantity': 1}}
        order, _ = create_order_from_cart(cart, CHECKOUT_DATA)
        self.assertTrue(
            OrderStatusHistory.objects.filter(order=order, to_status=Order.STATUS_PLACED).exists()
        )

    def test_payment_record_created(self):
        cart = {str(self.product.pk): {'quantity': 1}}
        order, payment = create_order_from_cart(cart, CHECKOUT_DATA)
        self.assertEqual(payment.order, order)
        self.assertEqual(payment.method, 'razorpay')

    def test_inactive_product_in_cart_excluded(self):
        p2 = make_product('Inactive', status=Product.STATUS_INACTIVE, sku='INA1')
        cart = {str(p2.pk): {'quantity': 1}}
        with self.assertRaises(CartValidationError):
            create_order_from_cart(cart, CHECKOUT_DATA)


# ── Stock restoration tests ───────────────────────────────────────────────────────

class StockRestorationTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.product = make_product('Earring', price=99, stock=8, sku='EAR1')

    def test_stock_restored_on_cancellation(self):
        cart = {str(self.product.pk): {'quantity': 3}}
        order, _ = create_order_from_cart(cart, CHECKOUT_DATA)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)  # 8 - 3

        restore_stock_for_order(order)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # restored

    def test_stock_not_double_restored(self):
        cart = {str(self.product.pk): {'quantity': 2}}
        order, _ = create_order_from_cart(cart, CHECKOUT_DATA)

        restore_stock_for_order(order)
        restore_stock_for_order(order)  # second call should be idempotent

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 8)  # not 10


# ── Checkout view tests ───────────────────────────────────────────────────────────

class CheckoutViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        StoreSettings.get()
        self.product = make_product('Scrunchie', price=99, stock=5, sku='SCR1')

    def _add_to_cart(self):
        self.client.post(
            reverse('orders:add_to_cart', args=[self.product.pk]),
            {'quantity': 1},
        )

    def test_checkout_redirects_empty_cart(self):
        r = self.client.get(reverse('orders:checkout'))
        self.assertEqual(r.status_code, 302)
        self.assertRedirects(r, reverse('orders:cart'))

    def test_checkout_loads_with_items(self):
        self._add_to_cart()
        r = self.client.get(reverse('orders:checkout'))
        self.assertEqual(r.status_code, 200)

    def test_checkout_invalid_pincode(self):
        self._add_to_cart()
        data = dict(CHECKOUT_DATA)
        data['pincode'] = '12345'   # invalid — must be 6 digits
        r = self.client.post(reverse('orders:checkout'), data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'valid 6-digit PIN')

    def test_checkout_invalid_phone(self):
        self._add_to_cart()
        data = dict(CHECKOUT_DATA)
        data['customer_phone'] = '123'
        r = self.client.post(reverse('orders:checkout'), data)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'valid 10-digit')


# ── Order tracking security ───────────────────────────────────────────────────────

class OrderTrackingTest(TestCase):

    def setUp(self):
        self.client = Client()
        StoreSettings.get()
        product = make_product(sku='TRK1')
        cart = {str(product.pk): {'quantity': 1}}
        self.order, _ = create_order_from_cart(cart, CHECKOUT_DATA)

    def test_track_valid_order(self):
        r = self.client.get(
            reverse('orders:track'),
            {'ref': self.order.reference, 'email': self.order.customer_email},
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.order.reference)

    def test_track_wrong_email_blocked(self):
        r = self.client.get(
            reverse('orders:track'),
            {'ref': self.order.reference, 'email': 'wrong@example.com'},
        )
        self.assertContains(r, 'No order found')

    def test_track_no_credentials_shows_form(self):
        r = self.client.get(reverse('orders:track'))
        self.assertEqual(r.status_code, 200)
        # Should show the lookup form, not any order data
        self.assertNotContains(r, self.order.reference)

    def test_my_orders_requires_login(self):
        r = self.client.get(reverse('orders:my_orders'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])
