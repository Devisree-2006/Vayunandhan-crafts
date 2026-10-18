from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('cart/',                          views.cart,               name='cart'),
    path('cart/add/<int:product_id>/',     views.add_to_cart,        name='add_to_cart'),
    path('cart/update/',                   views.update_cart,        name='update_cart'),
    path('checkout/',                      views.checkout,           name='checkout'),
    path('confirmation/<str:order_ref>/',  views.order_confirmation, name='confirmation'),
    path('track/',                         views.track_order,        name='track'),
    path('my-orders/',                     views.my_orders,          name='my_orders'),
]
