# delivery/views.py
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from users.permissions import IsAdminUser
from users.permissions import IsDeliveryUser
from orders.models import Order
from .models import Delivery
from .serializers import DeliverySerializer
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

class DeliveryListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    serializer_class = DeliverySerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated(), IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Delivery.objects.all()
        elif user.role == 'delivery':
            return Delivery.objects.filter(delivery_person=user)
        return Delivery.objects.filter(order__customer=user)

    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"User {request.user.username} fetching deliveries")
            return self.list(request, *args, **kwargs)
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
    permission_classes = [IsAuthenticated, IsDeliveryUser]

    def get_queryset(self):
        return Delivery.objects.filter(delivery_person=self.request.user)

    def patch(self, request, *args, **kwargs):
        try:
            delivery = self.get_object()
            logger.info(f"Delivery person {request.user.username} updating delivery {delivery.id}")
            serializer = self.get_serializer(delivery, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            if delivery.status == 'delivered':
                delivery.order.status = 'delivered'
                delivery.order.save()
                logger.info(f"Order {delivery.order.id} status updated to delivered")
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
        if user.role == 'admin':
            return Delivery.objects.all()
        elif user.role == 'delivery':
            return Delivery.objects.filter(delivery_person=user)
        return Delivery.objects.filter(order__customer=user)

    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"User {request.user.username} retrieving delivery {kwargs.get('pk')}")
            return self.retrieve(request, *args, **kwargs)
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