"""
Store models: Category, Product, ProductImage, StoreSettings, StockMovement.
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse
from decimal import Decimal
import uuid


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['sort_order', 'name']
        indexes = [models.Index(fields=['slug'])]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('store:category', kwargs={'slug': self.slug})


class Product(models.Model):
    STATUS_ACTIVE = 'active'
    STATUS_INACTIVE = 'inactive'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active'),
        (STATUS_INACTIVE, 'Inactive'),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True, blank=True)
    sku = models.CharField(max_length=100, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, related_name='products'
    )
    description = models.TextField(blank=True)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    original_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        help_text='Strike-through price before discount'
    )
    cost_price = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        help_text='Internal cost — visible only to staff'
    )
    stock = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_best_seller = models.BooleanField(default=False)
    weight_grams = models.PositiveIntegerField(
        default=0, help_text='Packed weight in grams (for shipping)'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['status', 'stock']),
            models.Index(fields=['category', 'status']),
            models.Index(fields=['is_featured']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)
            slug = base
            n = 1
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('store:product_detail', kwargs={'slug': self.slug})

    @property
    def primary_image(self):
        img = self.images.filter(is_primary=True).first()
        if not img:
            img = self.images.first()
        return img

    @property
    def discount_percent(self):
        if self.original_price and self.original_price > self.selling_price:
            pct = (self.original_price - self.selling_price) / self.original_price * 100
            return int(pct)
        return 0

    @property
    def is_in_stock(self):
        return self.stock > 0

    @property
    def is_low_stock(self):
        return 0 < self.stock <= self.low_stock_threshold


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='images'
    )
    image = models.ImageField(upload_to='products/')
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['-is_primary', 'sort_order']

    def __str__(self):
        return f'{self.product.name} – image {self.pk}'

    def save(self, *args, **kwargs):
        # Ensure only one primary image per product
        if self.is_primary:
            ProductImage.objects.filter(
                product=self.product, is_primary=True
            ).exclude(pk=self.pk).update(is_primary=False)
        super().save(*args, **kwargs)


class StockMovement(models.Model):
    REASON_SALE = 'sale'
    REASON_RESTOCK = 'restock'
    REASON_ADJUSTMENT = 'adjustment'
    REASON_RETURN = 'return'
    REASON_RESERVED = 'reserved'
    REASON_RELEASE = 'release'
    REASON_CHOICES = [
        (REASON_SALE, 'Sale'),
        (REASON_RESTOCK, 'Restock'),
        (REASON_ADJUSTMENT, 'Manual Adjustment'),
        (REASON_RETURN, 'Return / Refund'),
        (REASON_RESERVED, 'Reserved'),
        (REASON_RELEASE, 'Reservation Released'),
    ]

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='stock_movements'
    )
    quantity_change = models.IntegerField(help_text='Positive = stock added; negative = stock deducted')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    note = models.CharField(max_length=255, blank=True)
    order_reference = models.CharField(max_length=60, blank=True)
    performed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.quantity_change >= 0 else ''
        return f'{self.product.name}: {sign}{self.quantity_change} ({self.reason})'


class StoreSettings(models.Model):
    """Singleton model for administrator-configurable store settings."""
    store_name = models.CharField(max_length=100, default='Vayunandhan Crafts')
    tagline = models.CharField(max_length=200, blank=True)
    logo = models.ImageField(upload_to='branding/', blank=True, null=True)
    favicon = models.ImageField(upload_to='branding/', blank=True, null=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    instagram_url = models.URLField(blank=True)
    facebook_url = models.URLField(blank=True)
    address = models.TextField(blank=True)
    upi_id = models.CharField(max_length=100, blank=True)
    upi_display_name = models.CharField(max_length=100, blank=True)
    upi_qr_code = models.ImageField(upload_to='branding/', blank=True, null=True)
    upi_payment_instructions = models.TextField(
        blank=True,
        default='Scan the QR code or use the UPI ID to complete your payment. '
                'Enter your transaction/reference number after payment.'
    )
    delivery_charge = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    free_delivery_above = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('499.00'),
        help_text='Order total above which delivery is free. Set 0 to always charge.'
    )
    # Notification toggles
    notify_order_created = models.BooleanField(default=True)
    notify_payment_confirmed = models.BooleanField(default=True)
    notify_order_dispatched = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Store Settings'
        verbose_name_plural = 'Store Settings'

    def __str__(self):
        return self.store_name

    @classmethod
    def get(cls):
        """Return the singleton settings object, creating it if necessary."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CustomerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True)
    default_address_line1 = models.CharField(max_length=255, blank=True)
    default_address_line2 = models.CharField(max_length=255, blank=True)
    default_city = models.CharField(max_length=100, blank=True)
    default_state = models.CharField(max_length=100, blank=True)
    default_pincode = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Profile – {self.user.get_full_name() or self.user.username}'
