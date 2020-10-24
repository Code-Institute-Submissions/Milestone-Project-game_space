from django.urls import path
from . import views
from .webhooks import webhook


urlpatterns = [
    path('checkout/', views.checkout, name="checkout"),
    path('get_discount/', views.get_discount, name="get_discount"),
    path('checkout_success/<order_number>',
         views.checkout_success, name="checkout_success"),
    path('wh/', webhook, name="webhook"),
]
