from django.urls import path
from .views import PaymentListView, PaymentCallbackView, PaymentStatusView

urlpatterns = [
    path('payments/', PaymentListView.as_view(), name='payment-list'),
    path('payments/<int:id>/', PaymentStatusView.as_view(), name='payment-status'),
    path('payment/callback/', PaymentCallbackView.as_view(), name='payment-callback'),
]