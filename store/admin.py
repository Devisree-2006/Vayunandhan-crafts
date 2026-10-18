from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Product, ProductImage, StockMovement, StoreSettings, CustomerProfile


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'alt_text', 'is_primary', 'sort_order')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name',)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'sku', 'category', 'selling_price', 'stock',
        'status', 'is_featured', 'is_new_arrival', 'thumbnail'
    )
    list_editable = ('status', 'is_featured', 'is_new_arrival', 'stock')
    list_filter = ('status', 'category', 'is_featured', 'is_new_arrival')
    search_fields = ('name', 'sku', 'description')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductImageInline]
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Basic Info', {'fields': ('name', 'slug', 'sku', 'category', 'description')}),
        ('Pricing', {'fields': ('selling_price', 'original_price', 'cost_price')}),
        ('Inventory', {'fields': ('stock', 'low_stock_threshold', 'weight_grams')}),
        ('Flags', {'fields': ('status', 'is_featured', 'is_new_arrival', 'is_best_seller')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def thumbnail(self, obj):
        img = obj.primary_image
        if img:
            return format_html('<img src="{}" style="height:40px;border-radius:4px;">', img.image.url)
        return '—'
    thumbnail.short_description = 'Image'


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity_change', 'reason', 'order_reference', 'performed_by', 'created_at')
    list_filter = ('reason',)
    search_fields = ('product__name', 'order_reference')
    readonly_fields = ('created_at',)


@admin.register(StoreSettings)
class StoreSettingsAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return not StoreSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone')
    search_fields = ('user__username', 'user__email', 'phone')
