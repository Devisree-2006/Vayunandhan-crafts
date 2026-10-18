"""
Tests for the payments app:
  - Razorpay signature verification (valid and forged)
  - Idempotent payment confirmation
  - Duplicate webhook event handling
  - Manual UPI submission and admin approval/rejection
  - Payment status guards
"""
import hashlib
import hmac
import json
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.conf import settings
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.urls import reverse

from store.models import Category, Product, StoreSettings
from orders.models import Order, OrderStatusHistory
from orders.services import create_order_from_cart
from payments.models import Payment, UpiPaymentDetail
from payments.services import (
    verify_razorpay_signature,
    verify_razorpay_webhook_signature,
    confirm_razorpay_payment,
    submit_upi_payment,
    approve_upi_payment,
    reject_upi_payment,
)


# ── Helpers ───────────────────────────────────────────────────────────────────────

def make_product(sku='PAY001'):
    cat, _ = Category.objects.get_or_create(name='Pay Cat', slug='pay-cat')
    return Product.objects.create(
        name='Payment Test Product', sku=sku,
        category=cat, selling_price=Decimal('199'),
        stock=20, status=Product.STATUS_ACTIVE,
    )


CHECKOUT = {
    'customer_name': 'Kavya R', 'customer_email': 'kavya@example.com',
    'customer_phone': '9000000001', 'address_line1': '1 Main St',
    'address_line2': '', 'city': 'Pune', 'state': 'Maharashtra',
    'pincode': '411001', 'delivery_instructions': '', 'payment_method': 'razorpay',
}

CHECKOUT_UPI = {**CHECKOUT, 'payment_method': 'upi_manual', 'customer_email': 'upi@example.com'}


@override_settings(
    RAZORPAY_KEY_SECRET='test_secret',
    RAZORPAY_WEBHOOK_SECRET='webhook_secret',
)
class RazorpaySignatureTest(TestCase):

    def _make_sig(self, order_id, payment_id, secret='test_secret'):
        msg = f'{order_id}|{payment_id}'
        return hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()

    def test_valid_signature_accepted(self):
        sig = self._make_sig('order_abc', 'pay_xyz')
        self.assertTrue(verify_razorpay_signature('order_abc', 'pay_xyz', sig))

    def test_forged_signature_rejected(self):
        self.assertFalse(
            verify_razorpay_signature('order_abc', 'pay_xyz', 'forged_sig')
        )

    def test_tampered_payment_id_rejected(self):
        sig = self._make_sig('order_abc', 'pay_xyz')
        self.assertFalse(
            verify_razorpay_signature('order_abc', 'pay_TAMPERED', sig)
        )

    def test_valid_webhook_signature(self):
        body = b'{"event":"payment.captured"}'
        expected = hmac.new(b'webhook_secret', body, hashlib.sha256).hexdigest()
        self.assertTrue(verify_razorpay_webhook_signature(body, expected))

    def test_invalid_webhook_signature(self):
        body = b'{"event":"payment.captured"}'
        self.assertFalse(verify_razorpay_webhook_signature(body, 'bad_sig'))


@override_settings(RAZORPAY_KEY_SECRET='test_secret')
class RazorpayConfirmTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        product = make_product('PAY002')
        order, payment = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT
        )
        self.order   = order
        self.payment = payment
        self.payment.razorpay_order_id = 'order_TEST001'
        self.payment.save()

    def _make_sig(self, order_id, payment_id):
        msg = f'{order_id}|{payment_id}'
        return hmac.new(b'test_secret', msg.encode(), hashlib.sha256).hexdigest()

    def test_valid_payment_confirmed(self):
        sig = self._make_sig('order_TEST001', 'pay_001')
        payment = confirm_razorpay_payment('order_TEST001', 'pay_001', sig)
        self.assertEqual(payment.status, Payment.STATUS_VERIFIED)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAYMENT_VERIFIED)

    def test_forged_payment_raises_value_error(self):
        with self.assertRaises(ValueError):
            confirm_razorpay_payment('order_TEST001', 'pay_001', 'bad_sig')

    def test_payment_status_set_failed_on_bad_sig(self):
        try:
            confirm_razorpay_payment('order_TEST001', 'pay_001', 'bad_sig')
        except ValueError:
            pass
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_FAILED)

    def test_idempotent_already_verified(self):
        """Calling confirm twice should not raise and should return the same payment."""
        sig = self._make_sig('order_TEST001', 'pay_001')
        p1 = confirm_razorpay_payment('order_TEST001', 'pay_001', sig)
        p2 = confirm_razorpay_payment('order_TEST001', 'pay_001', sig)
        self.assertEqual(p1.pk, p2.pk)
        self.assertEqual(p2.status, Payment.STATUS_VERIFIED)

    def test_duplicate_webhook_event_skipped(self):
        sig = self._make_sig('order_TEST001', 'pay_001')
        confirm_razorpay_payment('order_TEST001', 'pay_001', sig, event_id='evt_001')
        # Second call with same event_id — should not raise or double-process
        p = confirm_razorpay_payment('order_TEST001', 'pay_001', sig, event_id='evt_001')
        self.assertEqual(p.status, Payment.STATUS_VERIFIED)

    def test_unknown_razorpay_order_raises(self):
        with self.assertRaises(ValueError):
            confirm_razorpay_payment('order_UNKNOWN', 'pay_001', 'sig')


class RazorpayWebhookViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        StoreSettings.get()
        product = make_product('WHK001')
        order, payment = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT
        )
        self.order   = order
        self.payment = payment
        self.payment.razorpay_order_id = 'order_WHK001'
        self.payment.save()

    def _webhook_sig(self, body: bytes) -> str:
        secret = settings.RAZORPAY_WEBHOOK_SECRET or 'wh_secret'
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    @override_settings(RAZORPAY_WEBHOOK_SECRET='wh_secret')
    def test_webhook_captured_verifies_payment(self):
        payload = json.dumps({
            'event': 'payment.captured',
            'id':    'evt_WHK001',
            'payload': {
                'payment': {
                    'entity': {
                        'id':       'pay_WHK001',
                        'order_id': 'order_WHK001',
                    }
                }
            }
        }).encode()
        sig = self._webhook_sig(payload)
        r = self.client.post(
            reverse('payments:razorpay_webhook'),
            data=payload,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )
        self.assertEqual(r.status_code, 200)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_VERIFIED)

    @override_settings(RAZORPAY_WEBHOOK_SECRET='wh_secret')
    def test_webhook_bad_signature_rejected(self):
        payload = b'{"event":"payment.captured"}'
        r = self.client.post(
            reverse('payments:razorpay_webhook'),
            data=payload,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE='badsig',
        )
        self.assertEqual(r.status_code, 400)


class UpiPaymentTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        product = make_product('UPI001')
        order, payment = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT_UPI
        )
        self.order   = order
        self.payment = payment
        self.admin   = User.objects.create_user('admin', is_staff=True, password='pass')

    def test_submit_upi_creates_detail(self):
        detail = submit_upi_payment(self.payment, 'TXN1234567')
        self.assertIsInstance(detail, UpiPaymentDetail)
        self.assertEqual(detail.upi_transaction_id, 'TXN1234567')

    def test_submit_upi_sets_verification_pending(self):
        submit_upi_payment(self.payment, 'TXN1234567')
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_VERIFICATION_PENDING)

    def test_submit_updates_order_status(self):
        submit_upi_payment(self.payment, 'TXN1234567')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAYMENT_VERIFICATION_PENDING)

    def test_admin_approve_verifies_payment(self):
        submit_upi_payment(self.payment, 'TXN1234567')
        approve_upi_payment(self.payment, self.admin)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_VERIFIED)
        self.assertEqual(self.payment.verified_by, self.admin)

    def test_admin_approve_advances_order(self):
        submit_upi_payment(self.payment, 'TXN1234567')
        approve_upi_payment(self.payment, self.admin)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAYMENT_VERIFIED)

    def test_admin_reject_cancels_order(self):
        submit_upi_payment(self.payment, 'TXN1234567')
        reject_upi_payment(self.payment, self.admin, 'Could not verify')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_CANCELLED)

    def test_admin_reject_restores_stock(self):
        product = Product.objects.get(sku='UPI001')
        stock_before = product.stock  # after order creation stock was deducted
        submit_upi_payment(self.payment, 'TXN1234567')
        reject_upi_payment(self.payment, self.admin)
        product.refresh_from_db()
        self.assertEqual(product.stock, stock_before + 1)

    def test_approval_idempotent(self):
        submit_upi_payment(self.payment, 'TXN1234567')
        approve_upi_payment(self.payment, self.admin)
        approve_upi_payment(self.payment, self.admin)  # second call
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_VERIFIED)

    def test_only_admin_can_approve(self):
        """Non-staff user should not reach approve endpoint."""
        regular = User.objects.create_user('regular', password='pass')
        client  = Client()
        client.login(username='regular', password='pass')
        submit_upi_payment(self.payment, 'TXN1234567')
        r = client.post(
            reverse('dashboard:verify_upi_payment', args=[self.payment.pk]),
            {'action': 'approve'},
        )
        # Should redirect to login or store home (not 200 with approval)
        self.assertIn(r.status_code, [302, 403])
        self.payment.refresh_from_db()
        self.assertNotEqual(self.payment.status, Payment.STATUS_VERIFIED)
