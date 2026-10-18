from django.contrib import admin
from .models import Payment, UpiPaymentDetail


class UpiDetailInline(admin.StackedInline):
    model = UpiPaymentDetail
    extra = 0
    readonly_fields = ('submitted_at',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('pk', 'order', 'method', 'amount', 'status', 'created_at')
    list_filter = ('method', 'status')
    search_fields = ('order__reference', 'razorpay_payment_id', 'razorpay_order_id')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [UpiDetailInline]
