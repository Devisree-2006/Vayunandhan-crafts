from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('<str:order_ref>/',             views.payment_page,       name='payment_page'),
    path('<str:order_ref>/<str:result>/',views.payment_result,     name='payment_result'),
    path('razorpay/initiate/',           views.razorpay_initiate,  name='razorpay_initiate'),
    path('razorpay/callback/',           views.razorpay_callback,  name='razorpay_callback'),
    path('razorpay/webhook/',            views.razorpay_webhook,   name='razorpay_webhook'),
    path('upi/submit/',                  views.upi_submit,         name='upi_submit'),
]
