from django.contrib import admin
from .models import Order, OrderItem, OrderStatusHistory, Shipment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name', 'product_sku', 'unit_price', 'quantity', 'item_discount')
    can_delete = False


class OrderStatusHistoryInline(admin.TabularInline):
    model = OrderStatusHistory
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'note', 'changed_by', 'created_at')
    can_delete = False


class ShipmentInline(admin.StackedInline):
    model = Shipment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'reference', 'customer_name', 'customer_phone',
        'total_amount', 'status', 'created_at'
    )
    list_filter = ('status', 'created_at')
    search_fields = ('reference', 'customer_name', 'customer_email', 'customer_phone')
    readonly_fields = ('reference', 'created_at', 'updated_at')
    inlines = [OrderItemInline, ShipmentInline, OrderStatusHistoryInline]
