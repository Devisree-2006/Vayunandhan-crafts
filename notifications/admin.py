from django.contrib import admin
from .models import NotificationLog


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ('order', 'channel', 'event', 'recipient', 'status', 'attempts', 'created_at')
    list_filter = ('channel', 'event', 'status')
    search_fields = ('order__reference', 'recipient')
    readonly_fields = ('idempotency_key', 'created_at', 'updated_at')
