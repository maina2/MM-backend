# delivery/urls.py
from django.urls import path
from .views import DeliveryListView, DeliveryUpdateView, DeliveryDetailView

urlpatterns = [
    path('manage/deliveries/', DeliveryListView.as_view(), name='manage-delivery-list'),
    path('manage/deliveries/<int:pk>/', DeliveryUpdateView.as_view(), name='manage-delivery-update'),
    path('manage/deliveries/<int:pk>/detail/', DeliveryDetailView.as_view(), name='manage-delivery-detail'),
    path('delivery/tasks/', DeliveryListView.as_view(), name='delivery-tasks-list'),
    path('delivery/tasks/<int:pk>/', DeliveryUpdateView.as_view(), name='delivery-tasks-update'),
    path('delivery/tasks/<int:pk>/detail/', DeliveryDetailView.as_view(), name='delivery-tasks-detail'),
]