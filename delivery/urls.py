from django.urls import path
from .views import DeliveryListView, DeliveryUpdateView, DeliveryDetailView

urlpatterns = [
    path('deliveries/', DeliveryListView.as_view(), name='delivery-list'),
    path('deliveries/<int:pk>/', DeliveryUpdateView.as_view(), name='delivery-update'),
    path('deliveries/<int:pk>/detail/', DeliveryDetailView.as_view(), name='delivery-detail'),
]