"""
Payment models: Payment, UpiPaymentDetail.
"""

from django.db import models
from django.contrib.auth.models import User
from orders.models import Order
from decimal import Decimal


class Payment(models.Model):
    METHOD_RAZORPAY = 'razorpay'
    METHOD_UPI_MANUAL = 'upi_manual'
    METHOD_CHOICES = [
        (METHOD_RAZORPAY, 'Razorpay'),
        (METHOD_UPI_MANUAL, 'Manual UPI'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_VERIFICATION_PENDING = 'verification_pending'
    STATUS_VERIFIED = 'verified'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUNDED = 'refunded'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_VERIFICATION_PENDING, 'Verification Pending'),
        (STATUS_VERIFIED, 'Verified / Paid'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=5, default='INR')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)

    # Razorpay identifiers
    razorpay_order_id = models.CharField(max_length=100, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True)
    razorpay_signature = models.CharField(max_length=255, blank=True)

    # Idempotency: track processed webhook/callback event IDs
    last_webhook_event_id = models.CharField(max_length=100, blank=True)

    # Audit
    verified_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_payments'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['razorpay_order_id']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'Payment {self.pk} – {self.order.reference} – {self.get_status_display()}'

    @property
    def is_paid(self):
        return self.status == self.STATUS_VERIFIED


class UpiPaymentDetail(models.Model):
    """Extra details collected for manual UPI payments."""
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='upi_detail')
    upi_transaction_id = models.CharField(max_length=100, blank=True)
    screenshot = models.ImageField(upload_to='upi_screenshots/', blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'UPI detail for payment {self.payment_id}'
