from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import OrderListView, OrderDetailView,CheckoutView,PaymentCallbackView,AdminOrderViewSet,BranchListView,BranchUpdateView,BranchDetailView,BranchCreateListView


router = DefaultRouter()
router.register(r'orders', AdminOrderViewSet, basename='admin-orders')

urlpatterns = [
    path('manage/', include(router.urls)),
    path('orders-list/', OrderListView.as_view(), name='order-list'),
    path('orders-details/<int:id>/', OrderDetailView.as_view(), name='order-detail'),
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('payment-callback/', PaymentCallbackView.as_view(), name='payment-callback'),
    path('branches/', BranchListView.as_view(), name='branch-list'),
    path('branches/<int:pk>/', BranchDetailView.as_view(), name='branch-detail'),
    path('admin/branches/', BranchCreateListView.as_view(), name='admin-branch-list-create'),
    path('admin/branches/<int:pk>/', BranchUpdateView.as_view(), name='admin-branch-update'),



]