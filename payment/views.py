# payments/views.py
from rest_framework import viewsets, status
from rest_framework.permissions import IsAdminUser
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from .models import Payment
from .serializers import PaymentSerializer
from rest_framework.response import Response

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 12
    page_size_query_param = 'page_size'
    max_page_size = 100

class AdminPaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all().select_related('order', 'order__customer').order_by('-created_at')
    serializer_class = PaymentSerializer
    permission_classes = [IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['order__id', 'phone_number']
    ordering_fields = ['created_at', 'amount', 'status']
    ordering = ['-created_at']

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payment = serializer.save()
        payment.sync_order_status()  # Sync payment status with order
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)