from django.urls import path
from .views import DeliveryListView, DeliveryUpdateView

urlpatterns = [
    path('deliveries/', DeliveryListView.as_view(), name='delivery-list'),
    path('deliveries/<int:pk>/', DeliveryUpdateView.as_view(), name='delivery-update'),
]