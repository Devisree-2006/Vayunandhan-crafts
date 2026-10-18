"""
Order models: Order, OrderItem, OrderStatusHistory, Shipment.
"""

from django.db import models
from django.contrib.auth.models import User
from store.models import Product
from decimal import Decimal
import uuid


def _order_ref():
    """Generate a short non-guessable order reference like VC-3F8A2B."""
    return 'VC-' + uuid.uuid4().hex[:6].upper()


class Order(models.Model):
    # ── Fulfilment statuses ─────────────────────────────────────────────────────
    STATUS_PLACED = 'placed'
    STATUS_PAYMENT_PENDING = 'payment_pending'
    STATUS_PAYMENT_VERIFICATION_PENDING = 'payment_verification_pending'
    STATUS_PAYMENT_VERIFIED = 'payment_verified'
    STATUS_PROCESSING = 'processing'
    STATUS_PACKED = 'packed'
    STATUS_DISPATCHED = 'dispatched'
    STATUS_OUT_FOR_DELIVERY = 'out_for_delivery'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'
    STATUS_REFUND_PENDING = 'refund_pending'
    STATUS_REFUNDED = 'refunded'

    STATUS_CHOICES = [
        (STATUS_PLACED, 'Order Placed'),
        (STATUS_PAYMENT_PENDING, 'Payment Pending'),
        (STATUS_PAYMENT_VERIFICATION_PENDING, 'Payment Verification Pending'),
        (STATUS_PAYMENT_VERIFIED, 'Payment Verified'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_PACKED, 'Packed'),
        (STATUS_DISPATCHED, 'Dispatched'),
        (STATUS_OUT_FOR_DELIVERY, 'Out for Delivery'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_REFUND_PENDING, 'Refund Pending'),
        (STATUS_REFUNDED, 'Refunded'),
    ]

    # Allowed next statuses per current status
    VALID_TRANSITIONS = {
        STATUS_PLACED: [STATUS_PAYMENT_PENDING, STATUS_PAYMENT_VERIFICATION_PENDING, STATUS_CANCELLED],
        STATUS_PAYMENT_PENDING: [STATUS_PAYMENT_VERIFIED, STATUS_CANCELLED],
        STATUS_PAYMENT_VERIFICATION_PENDING: [STATUS_PAYMENT_VERIFIED, STATUS_CANCELLED],
        STATUS_PAYMENT_VERIFIED: [STATUS_PROCESSING, STATUS_CANCELLED],
        STATUS_PROCESSING: [STATUS_PACKED, STATUS_CANCELLED],
        STATUS_PACKED: [STATUS_DISPATCHED, STATUS_CANCELLED],
        STATUS_DISPATCHED: [STATUS_OUT_FOR_DELIVERY, STATUS_DELIVERED],
        STATUS_OUT_FOR_DELIVERY: [STATUS_DELIVERED],
        STATUS_DELIVERED: [STATUS_REFUND_PENDING],
        STATUS_CANCELLED: [STATUS_REFUND_PENDING],
        STATUS_REFUND_PENDING: [STATUS_REFUNDED],
        STATUS_REFUNDED: [],
    }

    reference = models.CharField(max_length=20, unique=True, default=_order_ref, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')

    # Customer snapshot (captured at checkout — safe even if user changes details later)
    customer_name = models.CharField(max_length=200)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)

    # Delivery address snapshot
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)
    delivery_instructions = models.TextField(blank=True)

    # Financials (all stored as snapshots at time of order)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default=STATUS_PLACED)

    # Internal admin note
    admin_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['status']),
            models.Index(fields=['customer_email']),
            models.Index(fields=['customer_phone']),
        ]

    def __str__(self):
        return f'Order {self.reference} – {self.customer_name}'

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])

    def get_status_display_class(self):
        mapping = {
            self.STATUS_PLACED: 'info',
            self.STATUS_PAYMENT_PENDING: 'warning',
            self.STATUS_PAYMENT_VERIFICATION_PENDING: 'warning',
            self.STATUS_PAYMENT_VERIFIED: 'success',
            self.STATUS_PROCESSING: 'primary',
            self.STATUS_PACKED: 'primary',
            self.STATUS_DISPATCHED: 'primary',
            self.STATUS_OUT_FOR_DELIVERY: 'info',
            self.STATUS_DELIVERED: 'success',
            self.STATUS_CANCELLED: 'danger',
            self.STATUS_REFUND_PENDING: 'warning',
            self.STATUS_REFUNDED: 'secondary',
        }
        return mapping.get(self.status, 'secondary')


class OrderItem(models.Model):
    """
    Snapshot of a product line at the moment of purchase.
    Product references are kept for reporting but prices are immutable snapshots.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, related_name='order_items'
    )
    # Snapshots — never change these after order creation
    product_name = models.CharField(max_length=255)
    product_sku = models.CharField(max_length=100, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    item_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        indexes = [models.Index(fields=['order'])]

    def __str__(self):
        return f'{self.product_name} x{self.quantity}'

    @property
    def subtotal(self):
        return self.unit_price * self.quantity


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='history')
    from_status = models.CharField(max_length=40, blank=True)
    to_status = models.CharField(max_length=40)
    note = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.order.reference}: {self.from_status} → {self.to_status}'


class Shipment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipment')
    courier_name = models.CharField(max_length=100, blank=True)
    awb_number = models.CharField(max_length=100, blank=True, verbose_name='AWB / Tracking No.')
    tracking_url = models.URLField(blank=True)
    dispatch_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Shipment for {self.order.reference}'

    def get_tracking_link(self):
        if self.tracking_url and self.awb_number:
            return self.tracking_url
        return None
