from rest_framework import status, viewsets
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, UpdateModelMixin, RetrieveModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from users.permissions import IsAdminUser, IsDeliveryUser
from orders.models import Order
from .models import Delivery
from .serializers import DeliverySerializer
import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class DeliveryPersonViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.select_related('order', 'delivery_person').all()
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated, IsDeliveryUser]

    def get_queryset(self):
        """Return deliveries assigned to the requesting delivery person."""
        return self.queryset.filter(delivery_person=self.request.user)

    def get_serializer_class(self):
        """Use RouteOptimizationSerializer for optimize_route action."""
        if self.action == 'optimize_route':
            return RouteOptimizationSerializer
        return DeliverySerializer

    @action(detail=False, methods=['post'], url_path='optimize-route')
    def optimize_route(self, request):
        """
        Compute optimized route for delivery person's assigned deliveries.
        Input: { start_location: [lat, lng], delivery_ids: [id1, id2, ...] }
        Output: { optimized_route: [[lat, lng], ...] }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_location = tuple(serializer.validated_data['start_location'])
        delivery_ids = serializer.validated_data['delivery_ids']

        # Fetch deliveries
        deliveries = Delivery.objects.filter(id__in=delivery_ids, delivery_person=request.user)

        # Ensure all deliveries have coordinates
        locations = []
        for delivery in deliveries:
            if delivery.latitude is None or delivery.longitude is None:
                # Reuse Nominatim reverse geocoding logic from DeliverySerializer
                cache_key = f"geocode_{delivery.delivery_address}"
                cached_coords = cache.get(cache_key)
                if cached_coords:
                    delivery.latitude, delivery.longitude = cached_coords
                else:
                    for attempt in range(3):
                        try:
                            response = requests.get(
                                f"https://nominatim.openstreetmap.org/search?q={delivery.delivery_address}&format=json",
                                headers={'User-Agent': 'MuindiMwesiApp/1.0'},
                                timeout=5
                            )
                            response.raise_for_status()
                            results = response.json()
                            if results:
                                delivery.latitude = float(results[0]['lat'])
                                delivery.longitude = float(results[0]['lon'])
                                cache.set(cache_key, (delivery.latitude, delivery.longitude), timeout=86400)
                                break
                            else:
                                logger.warning(f"No coordinates found for {delivery.delivery_address}")
                                return Response(
                                    {"error": f"Unable to geocode address for delivery {delivery.id}"},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                        except requests.RequestException as e:
                            logger.error(f"Geocoding attempt {attempt + 1} failed for {delivery.delivery_address}: {str(e)}")
                            if attempt < 2:
                                sleep(1)
                            else:
                                return Response(
                                    {"error": f"Geocoding failed for delivery {delivery.id}"},
                                    status=status.HTTP_400_BAD_REQUEST
                                )
                delivery.save()
            locations.append((delivery.latitude, delivery.longitude))

        # Compute route
        try:
            route = compute_shortest_route(start_location, locations)
            if route:
                logger.info(f"Route computed for user {request.user.username} with {len(delivery_ids)} deliveries")
                return Response({"optimized_route": route})
            logger.error(f"Route computation failed for user {request.user.username}")
            return Response(
                {"error": "Unable to compute route"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Route computation error for user {request.user.username}: {str(e)}")
            return Response(
                {"error": f"Route computation failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
class DeliveryListView(GenericAPIView, ListModelMixin):
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == 'admin':
            return Delivery.objects.select_related('order', 'delivery_person').all()
        elif user.role == 'delivery':
            return Delivery.objects.select_related('order', 'delivery_person').filter(delivery_person=user)
        return Delivery.objects.select_related('order', 'delivery_person').filter(order__customer=user)

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

class DeliveryUpdateView(GenericAPIView, UpdateModelMixin):
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated, IsDeliveryUser]

    def get_queryset(self):
        return Delivery.objects.filter(delivery_person=self.request.user)

    def patch(self, request, *args, **kwargs):
        try:
            delivery = self.get_object()
            logger.info(f"Delivery person {request.user.username} updating delivery {delivery.id}")
            if set(request.data.keys()) - {'status'}:
                logger.warning(f"Invalid fields in update by {request.user.username}: {request.data.keys()}")
                return Response(
                    {"error": "Only status can be updated"},
                    status=status.HTTP_400_BAD_REQUEST
                )
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
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Delivery.DoesNotExist:
            logger.error(f"Delivery {kwargs.get('pk')} not found")
            return Response({"error": "Delivery not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Failed to update delivery {kwargs.get('pk')}: {str(e)}")
            return Response({"error": f"Failed to update delivery: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeliveryDetailView(GenericAPIView, RetrieveModelMixin):
    serializer_class = DeliverySerializer
    permission_classes = [IsAuthenticated, IsDeliveryUser]

    def get_queryset(self):
        return Delivery.objects.select_related('order', 'delivery_person').filter(delivery_person=self.request.user)

    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"User {request.user.username} retrieving delivery {kwargs.get('pk')}")
            return self.retrieve(request, *args, **kwargs)
        except Delivery.DoesNotExist:
            logger.error(f"Delivery {kwargs.get('pk')} not found")
            return Response({"error": "Delivery not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Failed to retrieve delivery {kwargs.get('pk')}: {str(e)}")
            return Response({"error": f"Failed to retrieve delivery: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeliveryAdminViewSet(viewsets.ModelViewSet):
    queryset = Delivery.objects.select_related('order', 'delivery_person').all()
    serializer_class = DeliverySerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'delivery_person', 'order__id']
    search_fields = ['delivery_address', 'order__id']
    ordering_fields = ['created_at', 'updated_at', 'estimated_delivery_time']
    ordering = ['-created_at']

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            order = serializer.validated_data['order']
            if hasattr(order, 'delivery'):
                logger.warning(f"Delivery already exists for order {order.id}")
                return Response(
                    {"error": "A delivery already exists for this order"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(f"Delivery created: ID {serializer.instance.id} for Order {order.id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except ValidationError as e:
            logger.error(f"Error creating delivery: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            self.perform_update(serializer)
            logger.info(f"Delivery {instance.id} updated by admin {request.user.username}")
            return Response(serializer.data)
        except ValidationError as e:
            logger.error(f"Error updating delivery {instance.id}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='assign-delivery-person')
    def assign_delivery_person(self, request, pk=None):
        delivery = self.get_object()
        delivery_person_id = request.data.get('delivery_person_id')
        if not delivery_person_id:
            return Response(
                {"error": "delivery_person_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            delivery_person = CustomUser.objects.get(id=delivery_person_id, role='delivery')
            delivery.delivery_person = delivery_person
            delivery.status = 'assigned'  # Update status to assigned
            delivery.save()
            serializer = self.get_serializer(delivery)
            logger.info(f"Delivery {delivery.id} assigned to delivery person {delivery_person.id}")
            return Response(serializer.data)
        except CustomUser.DoesNotExist:
            logger.error(f"Delivery person with ID {delivery_person_id} not found or not a delivery role")
            return Response(
                {"error": "Delivery person not found or invalid role"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error assigning delivery person: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='update-status')
    def update_delivery_status(self, request, pk=None):
        delivery = self.get_object()
        new_status = request.data.get('status')
        if not new_status:
            return Response(
                {"error": "status is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            delivery.update_status(new_status)
            if new_status == 'delivered':
                delivery.order.status = 'delivered'
                delivery.order.save()
                logger.info(f"Order {delivery.order.id} status updated to delivered")
            serializer = self.get_serializer(delivery)
            logger.info(f"Delivery {delivery.id} status updated to {new_status}")
            return Response(serializer.data)
        except ValueError as e:
            logger.error(f"Error updating delivery status for {delivery.id}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Unexpected error updating delivery status: {str(e)}")
            return Response({"error": "An unexpected error occurred"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.status not in ['pending', 'cancelled']:
            logger.warning(f"Attempt to delete delivery {instance.id} in {instance.status} status")
            return Response(
                {"error": "Can only delete deliveries in 'pending' or 'cancelled' status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            self.perform_destroy(instance)
            logger.info(f"Delivery {instance.id} deleted by admin {request.user.username}")
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            logger.error(f"Error deleting delivery {instance.id}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)