from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin, UpdateModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from products.permissions import IsAdminUser, IsDeliveryPerson
from orders.models import Order
from payment.models import Payment
from .models import Delivery
from .serializers import DeliverySerializer
from django.utils import timezone

class DeliveryListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    serializer_class = DeliverySerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Delivery.objects.all()
        elif user.is_delivery_person:
            return Delivery.objects.filter(delivery_person=user)
        return Delivery.objects.filter(order__customer=user)

    def get(self, request, *args, **kwargs):
        try:
            deliveries = self.get_queryset()
            serializer = self.get_serializer(deliveries, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch deliveries: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        try:
            order_id = request.data.get('order_id')
            delivery_address = request.data.get('delivery_address')
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')

            if not delivery_address:
                return Response(
                    {"error": "Delivery address is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            order = Order.objects.get(id=order_id)
            if order.customer != request.user:
                return Response(
                    {"error": "You can only create deliveries for your own orders"},
                    status=status.HTTP_403_FORBIDDEN
                )
            if hasattr(order, 'delivery'):
                return Response(
                    {"error": "A delivery already exists for this order"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Check if the order has a successful payment
            if not hasattr(order, 'payment'):
                return Response(
                    {"error": "No payment found for this order"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if order.payment.status != 'successful':
                return Response(
                    {"error": "Payment must be successful before creating a delivery"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create the delivery with latitude and longitude
            delivery = Delivery.objects.create(
                order=order,
                delivery_address=delivery_address,
                latitude=latitude,
                longitude=longitude,
                status='pending'
            )

            serializer = self.get_serializer(delivery)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to create delivery: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DeliveryUpdateView(GenericAPIView, UpdateModelMixin):
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated, IsDeliveryPerson]

    def get_queryset(self):
        return Delivery.objects.filter(delivery_person=self.request.user)

    def patch(self, request, *args, **kwargs):
        try:
            delivery = self.get_object()
            if 'status' in request.data:
                new_status = request.data.get('status')
                if new_status not in ['in_transit', 'delivered', 'cancelled']:
                    return Response(
                        {"error": "Invalid status. Allowed values: in_transit, delivered, cancelled"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                if new_status == 'delivered':
                    delivery.actual_delivery_time = timezone.now()

            serializer = self.get_serializer(delivery, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Delivery.DoesNotExist:
            return Response(
                {"error": "Delivery not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to update delivery: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )