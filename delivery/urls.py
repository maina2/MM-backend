from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeliveryListView, DeliveryUpdateView, DeliveryDetailView, DeliveryAdminViewSet

router = DefaultRouter()
router.register(r'admin/deliveries', DeliveryAdminViewSet, basename='delivery-admin')

urlpatterns = [
    # Delivery Person and Customer Endpoints
    path('delivery/tasks/', DeliveryListView.as_view(), name='delivery-tasks-list'),
    path('delivery/tasks/<int:pk>/', DeliveryUpdateView.as_view(), name='delivery-tasks-update'),
    path('delivery/tasks/<int:pk>/detail/', DeliveryDetailView.as_view(), name='delivery-tasks-detail'),
    path('', include(router.urls)),
]