from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from products.permissions import IsAdminUser, IsDeliveryPerson
from orders.models import Order
from payment.models import Payment
from users.models import CustomUser
from .models import Delivery
from .serializers import DeliverySerializer
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class DeliveryListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    serializer_class = DeliverySerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminUser()]  # Restrict creation to admins
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Delivery.objects.all()
        elif user.is_delivery_person:
            return Delivery.objects.filter(delivery_person=user)
        return Delivery.objects.filter(order__customer=user)

    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"User {request.user.username} fetching deliveries")
            deliveries = self.get_queryset()
            serializer = self.get_serializer(deliveries, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to fetch deliveries for user {request.user.username}: {str(e)}")
            return Response(
                {"error": f"Failed to fetch deliveries: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        try:
            logger.info(f"Admin {request.user.username} creating delivery for order {request.data.get('order_id')}")
            serializer = self.get_serializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)

            order = serializer.validated_data['order']
            if hasattr(order, 'delivery'):
                logger.warning(f"Delivery already exists for order {order.id}")
                return Response(
                    {"error": "A delivery already exists for this order"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Handle delivery person assignment
            delivery_person = serializer.validated_data.get('delivery_person')
            if delivery_person and not request.user.is_admin:
                logger.warning(f"Non-admin {request.user.username} attempted to assign delivery person")
                return Response(
                    {"error": "Only admins can assign a delivery person"},
                    status=status.HTTP_403_FORBIDDEN
                )

            delivery = serializer.save()
            logger.info(f"Delivery created: ID {delivery.id} for Order {order.id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Order.DoesNotExist:
            logger.error(f"Order {request.data.get('order_id')} not found")
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to create delivery: {str(e)}")
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
            logger.info(f"Delivery person {request.user.username} updating delivery {delivery.id}")
            
            if 'status' in request.data:
                new_status = request.data.get('status')
                delivery.update_status(new_status)  # Use model method for status transition
                if new_status == 'delivered':
                    delivery.order.status = 'completed'
                    delivery.order.save()
                    logger.info(f"Order {delivery.order.id} status updated to completed")

            serializer = self.get_serializer(delivery, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            logger.info(f"Delivery {delivery.id} updated to status {delivery.status}")
            return Response(serializer.data, status=status.HTTP_200_OK)

        except ValueError as e:
            logger.error(f"Invalid status transition for delivery {kwargs.get('pk')}: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Delivery.DoesNotExist:
            logger.error(f"Delivery {kwargs.get('pk')} not found")
            return Response(
                {"error": "Delivery not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to update delivery {kwargs.get('pk')}: {str(e)}")
            return Response(
                {"error": f"Failed to update delivery: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DeliveryDetailView(GenericAPIView, RetrieveModelMixin):
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Delivery.objects.all()
        elif user.is_delivery_person:
            return Delivery.objects.filter(delivery_person=user)
        return Delivery.objects.filter(order__customer=user)

    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"User {request.user.username} retrieving delivery {kwargs.get('pk')}")
            delivery = self.get_object()
            serializer = self.get_serializer(delivery)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Delivery.DoesNotExist:
            logger.error(f"Delivery {kwargs.get('pk')} not found")
            return Response(
                {"error": "Delivery not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to retrieve delivery {kwargs.get('pk')}: {str(e)}")
            return Response(
                {"error": f"Failed to retrieve delivery: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )