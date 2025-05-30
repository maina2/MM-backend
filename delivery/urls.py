from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    DeliveryListView,
    DeliveryUpdateView,
    DeliveryDetailView,
    DeliveryAdminViewSet,
    DeliveryPersonViewSet,  # New
)

router = DefaultRouter()
router.register(r'manage/deliveries', DeliveryAdminViewSet, basename='delivery-admin')
router.register(r'delivery-person', DeliveryPersonViewSet, basename='delivery-person')  # New

urlpatterns = [
    # Delivery Person Endpoints
    path('delivery/tasks/', DeliveryListView.as_view(), name='delivery-tasks-list'),
    path('delivery/tasks/<int:pk>/update/', DeliveryUpdateView.as_view(), name='delivery-tasks-update'),
    path('delivery/tasks/<int:pk>/detail/', DeliveryDetailView.as_view(), name='delivery-tasks-detail'),
    # Admin and Delivery Person Endpoints
    path('', include(router.urls)),
]