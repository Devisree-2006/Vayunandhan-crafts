from django.urls import path
from . import views

app_name = 'store'

urlpatterns = [
    path('',                     views.home,            name='home'),
    path('shop/',                views.shop,            name='shop'),
    path('shop/search/',         views.search,          name='search'),
    path('category/<slug:slug>/',views.category,        name='category'),
    path('product/<slug:slug>/', views.product_detail,  name='product_detail'),
    path('about/',               views.about,           name='about'),
    path('contact/',             views.contact,         name='contact'),
    path('faq/',                 views.faq,             name='faq'),
    path('shipping-policy/',     views.shipping_policy, name='shipping_policy'),
    path('returns-policy/',      views.returns_policy,  name='returns_policy'),
    path('privacy-policy/',      views.privacy_policy,  name='privacy_policy'),
    path('terms/',               views.terms,           name='terms'),
    path('accounts/register/',   views.register,        name='register'),
]
