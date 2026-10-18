"""
Tests for the dashboard app:
  - Staff-only access enforcement
  - Home, orders, products, inventory, earnings, settings pages
  - Order status update and validation
  - Stock adjustment
  - CSV export permissions
  - Revenue calculations
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from store.models import Category, Product, StoreSettings, StockMovement
from orders.models import Order, OrderStatusHistory
from orders.services import create_order_from_cart
from payments.models import Payment
from payments.services import confirm_razorpay_payment
from django.test import override_settings
import hashlib, hmac


# ── Helpers ───────────────────────────────────────────────────────────────────────

def make_product(sku='DSH001', price=199, stock=10):
    cat, _ = Category.objects.get_or_create(name='Dash Cat', slug='dash-cat')
    return Product.objects.create(
        name='Dashboard Product', sku=sku,
        category=cat, selling_price=Decimal(str(price)),
        stock=stock, status=Product.STATUS_ACTIVE,
    )


CHECKOUT = {
    'customer_name': 'Meena D', 'customer_email': 'meena@example.com',
    'customer_phone': '9222222222', 'address_line1': '7 Queen St',
    'address_line2': '', 'city': 'Hyderabad', 'state': 'Telangana',
    'pincode': '500001', 'delivery_instructions': '', 'payment_method': 'razorpay',
}


class StaffAccessTest(TestCase):
    """All dashboard URLs must redirect non-staff users."""

    def setUp(self):
        StoreSettings.get()
        self.staff  = User.objects.create_user('staff',  password='pass', is_staff=True)
        self.regular = User.objects.create_user('regular', password='pass', is_staff=False)

    def _urls_to_test(self):
        return [
            reverse('dashboard:home'),
            reverse('dashboard:orders'),
            reverse('dashboard:products'),
            reverse('dashboard:inventory'),
            reverse('dashboard:earnings'),
            reverse('dashboard:settings'),
            reverse('dashboard:payments'),
        ]

    def test_unauthenticated_redirected_to_login(self):
        c = Client()
        for url in self._urls_to_test():
            r = c.get(url)
            self.assertIn(r.status_code, [302], msg=f'{url} should redirect')
            self.assertIn('/login/', r['Location'], msg=f'{url} should go to login')

    def test_regular_user_redirected_to_home(self):
        c = Client()
        c.login(username='regular', password='pass')
        for url in self._urls_to_test():
            r = c.get(url)
            self.assertEqual(r.status_code, 302, msg=f'{url} should redirect non-staff')

    def test_staff_user_can_access(self):
        c = Client()
        c.login(username='staff', password='pass')
        for url in self._urls_to_test():
            r = c.get(url)
            self.assertEqual(r.status_code, 200, msg=f'{url} should be accessible to staff')


class DashboardHomeTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.staff  = User.objects.create_user('staff2', password='pass', is_staff=True)
        self.client = Client()
        self.client.login(username='staff2', password='pass')

    def test_dashboard_shows_order_count(self):
        product = make_product('DSH002')
        create_order_from_cart({str(product.pk): {'quantity': 1}}, CHECKOUT)
        r = self.client.get(reverse('dashboard:home'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '1')   # at least one order shown

    def test_dashboard_shows_revenue_zero_initially(self):
        r = self.client.get(reverse('dashboard:home'))
        self.assertContains(r, '₹0')


class OrderManagementTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.staff  = User.objects.create_user('staff3', password='pass', is_staff=True)
        self.client = Client()
        self.client.login(username='staff3', password='pass')
        product = make_product('DSH003')
        self.order, self.payment = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT
        )

    def test_orders_list_shows_order(self):
        r = self.client.get(reverse('dashboard:orders'))
        self.assertContains(r, self.order.reference)

    def test_order_detail_loads(self):
        r = self.client.get(
            reverse('dashboard:order_detail', args=[self.order.reference])
        )
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, self.order.customer_name)

    def test_valid_status_transition(self):
        # placed → payment_pending
        r = self.client.post(
            reverse('dashboard:update_order_status', args=[self.order.reference]),
            {'new_status': Order.STATUS_PAYMENT_PENDING, 'note': 'test'},
        )
        self.assertRedirects(r, reverse('dashboard:order_detail', args=[self.order.reference]))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAYMENT_PENDING)

    def test_invalid_status_transition_rejected(self):
        # placed → delivered is not valid
        self.client.post(
            reverse('dashboard:update_order_status', args=[self.order.reference]),
            {'new_status': Order.STATUS_DELIVERED, 'note': ''},
        )
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, Order.STATUS_DELIVERED)

    def test_status_history_recorded(self):
        self.client.post(
            reverse('dashboard:update_order_status', args=[self.order.reference]),
            {'new_status': Order.STATUS_PAYMENT_PENDING, 'note': 'moving forward'},
        )
        history = OrderStatusHistory.objects.filter(
            order=self.order, to_status=Order.STATUS_PAYMENT_PENDING
        )
        self.assertTrue(history.exists())
        self.assertEqual(history.first().changed_by, self.staff)

    def test_cancel_order_restores_stock(self):
        product = Product.objects.get(sku='DSH003')
        stock_after_order = product.stock  # deducted on order creation

        self.client.post(
            reverse('dashboard:update_order_status', args=[self.order.reference]),
            {'new_status': Order.STATUS_CANCELLED, 'note': 'cancelled'},
        )
        product.refresh_from_db()
        self.assertEqual(product.stock, stock_after_order + 1)


class ProductManagementTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.staff  = User.objects.create_user('staff4', password='pass', is_staff=True)
        self.client = Client()
        self.client.login(username='staff4', password='pass')
        Category.objects.get_or_create(name='Dash Cat', slug='dash-cat')

    def test_products_page_loads(self):
        r = self.client.get(reverse('dashboard:products'))
        self.assertEqual(r.status_code, 200)

    def test_add_product_form_loads(self):
        r = self.client.get(reverse('dashboard:product_add'))
        self.assertEqual(r.status_code, 200)

    def test_add_product_saves(self):
        cat = Category.objects.get(slug='dash-cat')
        r = self.client.post(reverse('dashboard:product_add'), {
            'name': 'New Bow Clip',
            'sku': 'NBC001',
            'category': cat.pk,
            'description': 'A cute bow clip',
            'selling_price': '129',
            'original_price': '',
            'cost_price': '50',
            'stock': '15',
            'low_stock_threshold': '3',
            'weight_grams': '20',
            'status': 'active',
        })
        self.assertRedirects(r, reverse('dashboard:products'))
        self.assertTrue(Product.objects.filter(sku='NBC001').exists())

    def test_add_product_missing_name_shows_error(self):
        r = self.client.post(reverse('dashboard:product_add'), {
            'name': '',
            'sku': 'ERR001',
            'selling_price': '99',
            'stock': '5',
        })
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'required')


class InventoryTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.staff   = User.objects.create_user('staff5', password='pass', is_staff=True)
        self.client  = Client()
        self.client.login(username='staff5', password='pass')
        self.product = make_product('INV001', stock=10)

    def test_inventory_page_loads(self):
        r = self.client.get(reverse('dashboard:inventory'))
        self.assertEqual(r.status_code, 200)

    def test_stock_adjust_increase(self):
        self.client.post(
            reverse('dashboard:adjust_stock', args=[self.product.pk]),
            {'qty_change': '5', 'note': 'Restock'},
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 15)

    def test_stock_adjust_decrease(self):
        self.client.post(
            reverse('dashboard:adjust_stock', args=[self.product.pk]),
            {'qty_change': '-3', 'note': 'Damaged'},
        )
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 7)

    def test_stock_movement_recorded(self):
        self.client.post(
            reverse('dashboard:adjust_stock', args=[self.product.pk]),
            {'qty_change': '10', 'note': 'Restock'},
        )
        m = StockMovement.objects.filter(
            product=self.product,
            reason=StockMovement.REASON_ADJUSTMENT,
        ).last()
        self.assertIsNotNone(m)
        self.assertEqual(m.quantity_change, 10)
        self.assertEqual(m.performed_by, self.staff)


class EarningsTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.staff  = User.objects.create_user('staff6', password='pass', is_staff=True)
        self.client = Client()
        self.client.login(username='staff6', password='pass')

    def test_earnings_page_loads(self):
        r = self.client.get(reverse('dashboard:earnings'))
        self.assertEqual(r.status_code, 200)

    def test_unverified_payment_not_in_revenue(self):
        """Pending payments must NOT appear in revenue totals."""
        product = make_product('ERN001', price=500)
        create_order_from_cart({str(product.pk): {'quantity': 1}}, CHECKOUT)
        r = self.client.get(reverse('dashboard:earnings'))
        # Revenue today should still be 0
        self.assertContains(r, '₹0')

    @override_settings(RAZORPAY_KEY_SECRET='test_secret')
    def test_verified_payment_counted_in_revenue(self):
        product = make_product('ERN002', price=299)
        order, payment = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT
        )
        payment.razorpay_order_id = 'order_ERN002'
        payment.save()

        sig = hmac.new(b'test_secret', b'order_ERN002|pay_ERN002', hashlib.sha256).hexdigest()
        confirm_razorpay_payment('order_ERN002', 'pay_ERN002', sig)

        r = self.client.get(reverse('dashboard:earnings'))
        self.assertContains(r, '299')


class CSVExportTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.staff   = User.objects.create_user('staff7', password='pass', is_staff=True)
        self.regular = User.objects.create_user('reg2',   password='pass', is_staff=False)

    def test_staff_can_download_csv(self):
        c = Client()
        c.login(username='staff7', password='pass')
        r = c.get(reverse('dashboard:export_csv'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/csv')

    def test_non_staff_cannot_download_csv(self):
        c = Client()
        c.login(username='reg2', password='pass')
        r = c.get(reverse('dashboard:export_csv'))
        self.assertEqual(r.status_code, 302)

    def test_unauthenticated_cannot_download_csv(self):
        c = Client()
        r = c.get(reverse('dashboard:export_csv'))
        self.assertEqual(r.status_code, 302)
