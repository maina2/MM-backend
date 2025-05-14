from django.urls import path
from .views import OrderListView, OrderDetailView,CheckoutView,PaymentCallbackView

urlpatterns = [
    path('orders-list/', OrderListView.as_view(), name='order-list'),
    path('orders-details/<int:id>/', OrderDetailView.as_view(), name='order-detail'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment-callback'),



]