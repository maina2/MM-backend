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
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework import viewsets, status
from products.permissions import IsAdminUser
from rest_framework.decorators import action

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


class DeliveryAdminViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.all()
    serializer_class = DeliverySerializer
    permission_classes = [IsAdminUser]  # Restrict to admin users only
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'delivery_person', 'order__id']
    search_fields = ['delivery_address', 'order__id']
    ordering_fields = ['created_at', 'updated_at', 'estimated_delivery_time']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Optimize queryset with select_related and prefetch_related to reduce database queries.
        """
        return Delivery.objects.select_related('order', 'delivery_person').all()

    def create(self, request, *args, **kwargs):
        """
        Create a new delivery. Ensures order has successful payment and is in 'processing' status.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except ValidationError as e:
            logger.error(f"Error creating delivery: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        """
        Update delivery details, including status and delivery person assignment.
        """
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_update(serializer)
            return Response(serializer.data)
        except ValidationError as e:
            logger.error(f"Error updating delivery {instance.id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='assign-delivery-person')
    def assign_delivery_person(self, request, pk=None):
        """
        Custom action to assign or reassign a delivery person.
        """
        delivery = self.get_object()
        delivery_person_id = request.data.get('delivery_person_id')
        if not delivery_person_id:
            return Response(
                {"detail": "delivery_person_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            delivery_person = CustomUser.objects.get(id=delivery_person_id, role='delivery')
            delivery.delivery_person = delivery_person
            delivery.save()
            serializer = self.get_serializer(delivery)
            return Response(serializer.data)
        except CustomUser.DoesNotExist:
            logger.error(f"Delivery person with ID {delivery_person_id} not found or not a delivery role")
            return Response(
                {"detail": "Delivery person not found or invalid role"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error assigning delivery person: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_delivery_status(self, request, pk=None):
        """
        Custom action to update delivery status with transition validation.
        """
        delivery = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {"detail": "status is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            delivery.update_status(new_status)
            serializer = self.get_serializer(delivery)
            return Response(serializer.data)
        except ValueError as e:
            logger.error(f"Error updating delivery status for {delivery.id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error updating delivery status: {str(e)}")
            return Response({"detail": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        """
        Allow deletion of deliveries only if they are in 'pending' or 'cancelled' status.
        """
        instance = self.get_object()
        if instance.status not in ['pending', 'cancelled']:
            logger.warning(f"Attempt to delete delivery {instance.id} in {instance.status} status")
            return Response(
                {"detail": "Can only delete deliveries in 'pending' or 'cancelled' status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting delivery {instance.id}: {str(e)}")
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)