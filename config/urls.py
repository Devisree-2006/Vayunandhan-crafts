"""
Root URL configuration for Vayunandhan Crafts.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('django-admin/', admin.site.urls),

    # Customer-facing store
    path('', include('store.urls', namespace='store')),

    # Orders
    path('orders/', include('orders.urls', namespace='orders')),

    # Payments
    path('payments/', include('payments.urls', namespace='payments')),

    # Notifications (webhooks)
    path('notifications/', include('notifications.urls', namespace='notifications')),

    # Admin dashboard
    path('dashboard/', include('dashboard.urls', namespace='dashboard')),

    # Django built-in auth (login/logout/password)
    path('accounts/', include('django.contrib.auth.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
