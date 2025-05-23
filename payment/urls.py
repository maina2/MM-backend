# payments/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import AdminPaymentViewSet

router = DefaultRouter()
router.register(r'payments', AdminPaymentViewSet, basename='admin-payments')

urlpatterns = [
    path('manage/', include(router.urls)),
]