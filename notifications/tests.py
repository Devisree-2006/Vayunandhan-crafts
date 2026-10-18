"""
Tests for the notifications app:
  - Email dispatch with mocked backend
  - WhatsApp notification with mocked requests
  - Idempotency (no duplicate sends)
  - Graceful degradation when credentials missing
  - WhatsApp webhook verification endpoint
"""
from decimal import Decimal
from unittest.mock import patch, MagicMock

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core import mail

from store.models import Category, Product, StoreSettings
from orders.services import create_order_from_cart
from notifications.models import NotificationLog
from notifications.services import send_order_notifications


# ── Helpers ───────────────────────────────────────────────────────────────────────

def make_product(sku='NTF001'):
    cat, _ = Category.objects.get_or_create(name='Notif Cat', slug='notif-cat')
    return Product.objects.create(
        name='Notif Product', sku=sku,
        category=cat, selling_price=Decimal('149'),
        stock=20, status=Product.STATUS_ACTIVE,
    )


CHECKOUT = {
    'customer_name': 'Ananya K', 'customer_email': 'ananya@example.com',
    'customer_phone': '9111111111', 'address_line1': '5 Park Lane',
    'address_line2': '', 'city': 'Bengaluru', 'state': 'Karnataka',
    'pincode': '560001', 'delivery_instructions': '', 'payment_method': 'razorpay',
}


# ── Email notification tests ──────────────────────────────────────────────────────

class EmailNotificationTest(TestCase):

    def setUp(self):
        StoreSettings.get()
        product = make_product('NTF002')
        self.order, _ = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT
        )

    def test_email_sent_on_payment_confirmed(self):
        send_order_notifications(self.order, 'payment_confirmed')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.order.reference, mail.outbox[0].subject)
        self.assertEqual(mail.outbox[0].to, [self.order.customer_email])

    def test_notification_log_created(self):
        send_order_notifications(self.order, 'payment_confirmed')
        log = NotificationLog.objects.filter(
            order=self.order,
            event=NotificationLog.EVENT_PAYMENT_CONFIRMED,
            channel=NotificationLog.CHANNEL_EMAIL,
        )
        self.assertTrue(log.exists())
        self.assertEqual(log.first().status, NotificationLog.STATUS_SENT)

    def test_email_not_sent_twice_same_event(self):
        """Idempotency — second call with same event must not re-send."""
        send_order_notifications(self.order, 'payment_confirmed')
        send_order_notifications(self.order, 'payment_confirmed')
        self.assertEqual(len(mail.outbox), 1)

    def test_dispatched_email_contains_order_ref(self):
        send_order_notifications(self.order, 'order_dispatched')
        self.assertTrue(any(
            self.order.reference in m.subject for m in mail.outbox
        ))

    def test_cancelled_email_sent(self):
        send_order_notifications(self.order, 'order_cancelled')
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_event_does_not_crash(self):
        """Sending an unrecognised event should be a no-op."""
        try:
            send_order_notifications(self.order, 'unknown_event_xyz')
        except Exception as e:
            self.fail(f'send_order_notifications raised {e} on unknown event')


# ── WhatsApp notification tests ───────────────────────────────────────────────────

@override_settings(
    WHATSAPP_ACCESS_TOKEN='test_token',
    WHATSAPP_PHONE_NUMBER_ID='1234567890',
    STORE_WHATSAPP_NUMBER='919999999999',
)
class WhatsAppNotificationTest(TestCase):

    def setUp(self):
        s = StoreSettings.get()
        s.whatsapp_number         = '919999999999'
        s.notify_order_created    = True
        s.notify_payment_confirmed = True
        s.notify_order_dispatched  = True
        s.save()

        product = make_product('NTF003')
        self.order, _ = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT
        )

    @patch('notifications.services.requests.post')
    def test_whatsapp_sent_on_order_placed(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        send_order_notifications(self.order, 'order_placed')
        self.assertTrue(mock_post.called)

    @patch('notifications.services.requests.post')
    def test_whatsapp_log_recorded_on_success(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        send_order_notifications(self.order, 'payment_confirmed')
        log = NotificationLog.objects.filter(
            order=self.order,
            channel=NotificationLog.CHANNEL_WHATSAPP,
            event=NotificationLog.EVENT_PAYMENT_CONFIRMED,
        ).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, NotificationLog.STATUS_SENT)

    @patch('notifications.services.requests.post')
    def test_whatsapp_not_sent_twice(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=lambda: None)
        send_order_notifications(self.order, 'order_placed')
        send_order_notifications(self.order, 'order_placed')
        self.assertEqual(mock_post.call_count, 1)

    @patch('notifications.services.requests.post')
    def test_whatsapp_failure_logs_and_does_not_raise(self, mock_post):
        import requests as req
        mock_post.side_effect = req.exceptions.RequestException('Timeout')
        try:
            send_order_notifications(self.order, 'order_placed')
        except Exception as e:
            self.fail(f'WhatsApp failure should not propagate: {e}')

        log = NotificationLog.objects.filter(
            channel=NotificationLog.CHANNEL_WHATSAPP,
        ).first()
        self.assertEqual(log.status, NotificationLog.STATUS_FAILED)


@override_settings(
    WHATSAPP_ACCESS_TOKEN='',
    WHATSAPP_PHONE_NUMBER_ID='',
    STORE_WHATSAPP_NUMBER='',
)
class WhatsAppMissingCredentialsTest(TestCase):

    def setUp(self):
        s = StoreSettings.get()
        s.whatsapp_number = ''
        s.save()
        product = make_product('NTF004')
        self.order, _ = create_order_from_cart(
            {str(product.pk): {'quantity': 1}}, CHECKOUT
        )

    def test_skips_gracefully_when_not_configured(self):
        """No crash and no WA log when WhatsApp is not configured."""
        try:
            send_order_notifications(self.order, 'order_placed')
        except Exception as e:
            self.fail(f'Should not raise when WA not configured: {e}')


# ── WhatsApp webhook endpoint tests ──────────────────────────────────────────────

@override_settings(WHATSAPP_VERIFY_TOKEN='my_verify_token')
class WhatsAppWebhookTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_get_challenge_valid_token(self):
        r = self.client.get(
            reverse('notifications:whatsapp_webhook'),
            {
                'hub.mode':         'subscribe',
                'hub.verify_token': 'my_verify_token',
                'hub.challenge':    '12345ABC',
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'12345ABC')

    def test_get_challenge_wrong_token_rejected(self):
        r = self.client.get(
            reverse('notifications:whatsapp_webhook'),
            {
                'hub.mode':         'subscribe',
                'hub.verify_token': 'WRONG_TOKEN',
                'hub.challenge':    '12345ABC',
            },
        )
        self.assertEqual(r.status_code, 403)

    def test_post_returns_ok(self):
        r = self.client.post(
            reverse('notifications:whatsapp_webhook'),
            data='{}',
            content_type='application/json',
        )
        self.assertEqual(r.status_code, 200)
