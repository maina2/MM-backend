# delivery/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DeliveryListView, DeliveryUpdateView, DeliveryDetailView

# Use GenericAPIView-based views directly
urlpatterns = [
    path('admin/deliveries/', DeliveryListView.as_view(), name='admin-delivery-list'),
    path('admin/deliveries/<int:pk>/', DeliveryUpdateView.as_view(), name='admin-delivery-update'),
    path('admin/deliveries/<int:pk>/detail/', DeliveryDetailView.as_view(), name='admin-delivery-detail'),
    path('delivery/tasks/', DeliveryListView.as_view(), name='delivery-tasks-list'),
    path('delivery/tasks/<int:pk>/', DeliveryUpdateView.as_view(), name='delivery-tasks-update'),
    path('delivery/tasks/<int:pk>/detail/', DeliveryDetailView.as_view(), name='delivery-tasks-detail'),
]