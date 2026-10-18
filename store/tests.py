"""
Tests for the store app:
  - Category and Product model behaviour
  - Product listing, filtering, search views
  - Context processors
  - Registration form
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from store.models import Category, Product, StoreSettings, CustomerProfile
from store.services import calculate_delivery_charge, build_cart_summary
from store.forms import CustomerRegistrationForm


# ── Helpers ───────────────────────────────────────────────────────────────────────

def make_category(name='Hair Clips', slug=None):
    return Category.objects.create(
        name=name,
        slug=slug or name.lower().replace(' ', '-'),
        is_active=True,
    )


def make_product(name='Test Clip', category=None, price=199, stock=10,
                 status=Product.STATUS_ACTIVE, sku=None):
    return Product.objects.create(
        name=name,
        sku=sku or f'SKU-{name[:8].upper().replace(" ","")}',
        category=category,
        selling_price=Decimal(str(price)),
        stock=stock,
        status=status,
    )


# ── Model tests ───────────────────────────────────────────────────────────────────

class ProductModelTest(TestCase):

    def setUp(self):
        self.cat = make_category()

    def test_slug_auto_generated(self):
        p = make_product('Beautiful Scrunchie', self.cat)
        self.assertEqual(p.slug, 'beautiful-scrunchie')

    def test_slug_unique_on_collision(self):
        p1 = make_product('Rose Clip', self.cat, sku='SKU001')
        p2 = make_product('Rose Clip', self.cat, sku='SKU002')
        self.assertNotEqual(p1.slug, p2.slug)

    def test_is_in_stock(self):
        p = make_product(stock=5)
        self.assertTrue(p.is_in_stock)

    def test_not_in_stock(self):
        p = make_product(stock=0)
        self.assertFalse(p.is_in_stock)

    def test_is_low_stock(self):
        p = make_product(stock=3)
        p.low_stock_threshold = 5
        p.save()
        self.assertTrue(p.is_low_stock)

    def test_discount_percent(self):
        p = make_product(price=150)
        p.original_price = Decimal('200')
        p.save()
        self.assertEqual(p.discount_percent, 25)

    def test_discount_percent_no_original(self):
        p = make_product(price=150)
        self.assertEqual(p.discount_percent, 0)

    def test_inactive_product_excluded_from_active_query(self):
        make_product('Active', status=Product.STATUS_ACTIVE, sku='A1')
        make_product('Inactive', status=Product.STATUS_INACTIVE, sku='I1')
        active = Product.objects.filter(status=Product.STATUS_ACTIVE)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().name, 'Active')


# ── View tests ────────────────────────────────────────────────────────────────────

class HomeViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        StoreSettings.get()  # ensure singleton exists

    def test_home_loads(self):
        r = self.client.get(reverse('store:home'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Vayunandhan Crafts')

    def test_home_shows_featured_products(self):
        cat = make_category()
        make_product('Featured Keychain', cat, sku='FK1')
        p = Product.objects.first()
        p.is_featured = True
        p.save()
        r = self.client.get(reverse('store:home'))
        self.assertContains(r, 'Featured Keychain')


class ShopViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        StoreSettings.get()
        self.cat = make_category('Scrunchies', 'scrunchies')
        make_product('Pink Scrunchie', self.cat, price=99, sku='PS1')
        make_product('Blue Scrunchie', self.cat, price=149, sku='BS1')
        make_product('Inactive Product', self.cat, status=Product.STATUS_INACTIVE, sku='IP1')

    def test_shop_loads(self):
        r = self.client.get(reverse('store:shop'))
        self.assertEqual(r.status_code, 200)

    def test_shop_excludes_inactive(self):
        r = self.client.get(reverse('store:shop'))
        self.assertNotContains(r, 'Inactive Product')

    def test_shop_shows_active_products(self):
        r = self.client.get(reverse('store:shop'))
        self.assertContains(r, 'Pink Scrunchie')
        self.assertContains(r, 'Blue Scrunchie')

    def test_category_filter(self):
        cat2 = make_category('Earrings', 'earrings')
        make_product('Gold Ear', cat2, sku='GE1')
        r = self.client.get(reverse('store:category', kwargs={'slug': 'scrunchies'}))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, 'Gold Ear')

    def test_sort_price_asc(self):
        r = self.client.get(reverse('store:shop') + '?sort=price_asc')
        self.assertEqual(r.status_code, 200)

    def test_search_finds_product(self):
        r = self.client.get(reverse('store:search') + '?q=Pink')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Pink Scrunchie')

    def test_search_no_results(self):
        r = self.client.get(reverse('store:search') + '?q=xyznotexist')
        self.assertContains(r, 'No results found')


class ProductDetailViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        StoreSettings.get()
        self.cat = make_category()
        self.product = make_product('Clay Charm', self.cat, sku='CC1')

    def test_detail_loads(self):
        r = self.client.get(self.product.get_absolute_url())
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Clay Charm')

    def test_inactive_product_returns_404(self):
        p = make_product('Hidden', status=Product.STATUS_INACTIVE, sku='HID1')
        r = self.client.get(p.get_absolute_url())
        self.assertEqual(r.status_code, 404)

    def test_out_of_stock_product_shows_label(self):
        p = make_product('OOS Product', stock=0, sku='OOS1')
        r = self.client.get(p.get_absolute_url())
        self.assertContains(r, 'Out of Stock')


# ── Delivery service tests ────────────────────────────────────────────────────────

class DeliveryChargeTest(TestCase):

    def setUp(self):
        s = StoreSettings.get()
        s.delivery_charge     = Decimal('49.00')
        s.free_delivery_above = Decimal('499.00')
        s.save()

    def test_delivery_charged_below_threshold(self):
        charge = calculate_delivery_charge(Decimal('300'))
        self.assertEqual(charge, Decimal('49.00'))

    def test_free_delivery_at_threshold(self):
        charge = calculate_delivery_charge(Decimal('499'))
        self.assertEqual(charge, Decimal('0.00'))

    def test_free_delivery_above_threshold(self):
        charge = calculate_delivery_charge(Decimal('750'))
        self.assertEqual(charge, Decimal('0.00'))


# ── Cart summary service tests ────────────────────────────────────────────────────

class CartSummaryTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        self.product = make_product('Resin Keychain', price=149, stock=10, sku='RK1')

    def test_empty_cart(self):
        s = build_cart_summary({})
        self.assertEqual(s['subtotal'], Decimal('0.00'))
        self.assertEqual(s['items'], [])

    def test_cart_with_one_item(self):
        cart = {str(self.product.pk): {'quantity': 2}}
        s = build_cart_summary(cart)
        self.assertEqual(len(s['items']), 1)
        self.assertEqual(s['subtotal'], Decimal('298.00'))

    def test_cart_clamps_qty_to_stock(self):
        cart = {str(self.product.pk): {'quantity': 99}}
        s = build_cart_summary(cart)
        self.assertEqual(s['items'][0]['quantity'], 10)

    def test_unavailable_product_excluded(self):
        inactive = make_product('Gone', status=Product.STATUS_INACTIVE, sku='GN1')
        cart = {str(inactive.pk): {'quantity': 1}}
        s = build_cart_summary(cart)
        self.assertEqual(s['items'], [])


# ── Registration form tests ───────────────────────────────────────────────────────

class RegistrationFormTest(TestCase):

    def _valid_data(self, **overrides):
        data = {
            'username':   'testuser',
            'first_name': 'Test',
            'last_name':  'User',
            'email':      'test@example.com',
            'phone':      '9876543210',
            'password1':  'Str0ngP@ss!',
            'password2':  'Str0ngP@ss!',
        }
        data.update(overrides)
        return data

    def test_valid_form(self):
        form = CustomerRegistrationForm(data=self._valid_data())
        self.assertTrue(form.is_valid(), form.errors)

    def test_passwords_must_match(self):
        form = CustomerRegistrationForm(data=self._valid_data(password2='Wrong'))
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)

    def test_email_required(self):
        form = CustomerRegistrationForm(data=self._valid_data(email=''))
        self.assertFalse(form.is_valid())

    def test_save_creates_profile(self):
        form = CustomerRegistrationForm(data=self._valid_data())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())
