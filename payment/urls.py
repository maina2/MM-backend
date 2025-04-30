from django.urls import path
from .views import PaymentListView, PaymentCallbackView

urlpatterns = [
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payment/callback/', PaymentCallbackView.as_view(), name='payment-callback'),
]