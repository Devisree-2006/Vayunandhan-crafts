from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('',                                       views.home,                 name='home'),
    # Orders
    path('orders/',                                views.orders,               name='orders'),
    path('orders/<str:order_ref>/',                views.order_detail,         name='order_detail'),
    path('orders/<str:order_ref>/status/',         views.update_order_status,  name='update_order_status'),
    path('orders/<str:order_ref>/shipment/',       views.update_shipment,      name='update_shipment'),
    # Payments
    path('payments/',                              views.payments,             name='payments'),
    path('payments/<int:payment_id>/verify/',      views.verify_upi_payment,   name='verify_upi_payment'),
    # Products
    path('products/',                              views.products,             name='products'),
    path('products/add/',                          views.product_form,         name='product_add'),
    path('products/<int:pk>/edit/',                views.product_form,         name='product_edit'),
    path('products/images/<int:image_id>/delete/', views.delete_product_image, name='delete_product_image'),
    # Inventory
    path('inventory/',                             views.inventory,            name='inventory'),
    path('inventory/<int:product_id>/adjust/',     views.adjust_stock,         name='adjust_stock'),
    # Earnings
    path('earnings/',                              views.earnings,             name='earnings'),
    path('earnings/export/',                       views.export_orders_csv,    name='export_csv'),
    # Settings
    path('settings/',                              views.settings_view,        name='settings'),
]
