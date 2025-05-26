from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, CheckoutView, PaymentCallbackView, BranchListCreateView, BranchDetailUpdateView

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='orders')

urlpatterns = [
    path('', include(router.urls)),
    path('orders/checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    path('branches/', BranchListCreateView.as_view(), name='branch-list-create'),
    path('branches/<int:pk>/', BranchDetailUpdateView.as_view(), name='branch-detail-update'),
]