"""
Notification outbox — tracks every email and WhatsApp message attempt.
Enables retry without duplication via idempotency keys.
"""

from django.db import models
from orders.models import Order


class NotificationLog(models.Model):
    CHANNEL_EMAIL = 'email'
    CHANNEL_WHATSAPP = 'whatsapp'
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, 'Email'),
        (CHANNEL_WHATSAPP, 'WhatsApp'),
    ]

    EVENT_ORDER_PLACED = 'order_placed'
    EVENT_PAYMENT_CONFIRMED = 'payment_confirmed'
    EVENT_PAYMENT_VERIFICATION_PENDING = 'payment_verification_pending'
    EVENT_PAYMENT_REJECTED = 'payment_rejected'
    EVENT_ORDER_DISPATCHED = 'order_dispatched'
    EVENT_ORDER_DELIVERED = 'order_delivered'
    EVENT_ORDER_CANCELLED = 'order_cancelled'
    EVENT_REFUNDED = 'refunded'
    EVENT_CHOICES = [
        (EVENT_ORDER_PLACED, 'Order Placed'),
        (EVENT_PAYMENT_CONFIRMED, 'Payment Confirmed'),
        (EVENT_PAYMENT_VERIFICATION_PENDING, 'Payment Verification Pending'),
        (EVENT_PAYMENT_REJECTED, 'Payment Rejected'),
        (EVENT_ORDER_DISPATCHED, 'Order Dispatched'),
        (EVENT_ORDER_DELIVERED, 'Order Delivered'),
        (EVENT_ORDER_CANCELLED, 'Order Cancelled'),
        (EVENT_REFUNDED, 'Refunded'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'
    STATUS_SKIPPED = 'skipped'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_SKIPPED, 'Skipped'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notifications')
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    event = models.CharField(max_length=40, choices=EVENT_CHOICES)
    recipient = models.CharField(max_length=255, help_text='Email address or WhatsApp number')
    idempotency_key = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    error_message = models.TextField(blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order', 'event', 'channel']),
            models.Index(fields=['idempotency_key']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.channel}/{self.event} for {self.order.reference} – {self.status}'
