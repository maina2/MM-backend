from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeliveryListView, DeliveryUpdateView, DeliveryDetailView, DeliveryAdminViewSet

router = DefaultRouter()
router.register(r'admin/deliveries', DeliveryAdminViewSet, basename='delivery-admin')

urlpatterns = [
    # Delivery Person Endpoints
    path('delivery/tasks/', DeliveryListView.as_view(), name='delivery-tasks-list'),
    path('delivery/tasks/<int:pk>/update/', DeliveryUpdateView.as_view(), name='delivery-tasks-update'),
    path('delivery/tasks/<int:pk>/detail/', DeliveryDetailView.as_view(), name='delivery-tasks-detail'),
    # Admin Endpoints
    path('', include(router.urls)),
]