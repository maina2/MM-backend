from rest_framework import serializers
import requests
from time import sleep
from django.core.cache import cache
from .models import Delivery
from orders.serializers import OrderSerializer
from users.serializers import CustomUserSerializer
from orders.models import Order
from users.models import CustomUser
import logging

logger = logging.getLogger(__name__)

class DeliverySerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), source='order', write_only=True
    )
    delivery_person = CustomUserSerializer(read_only=True)
    delivery_person_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role='delivery'),
        source='delivery_person',
        write_only=True,
        required=False,
        allow_null=True
    )
    latitude = serializers.FloatField(required=False, allow_null=True)
    longitude = serializers.FloatField(required=False, allow_null=True)

    class Meta:
        model = Delivery
        fields = [
            'id', 'order', 'order_id', 'delivery_person', 'delivery_person_id',
            'status', 'delivery_address', 'latitude', 'longitude',
            'estimated_delivery_time', 'actual_delivery_time', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'actual_delivery_time']

    def validate_order(self, order):
        if not hasattr(order, 'payment') or order.payment.status != 'successful':
            raise serializers.ValidationError("Order must have a successful payment")
        if order.status not in ['pending', 'processing']:
            raise serializers.ValidationError("Order must be in 'pending' or 'processing' status")
        return order

    def validate_latitude(self, value):
        return value  # Rely on model validators

    def validate_longitude(self, value):
        return value  # Rely on model validators

    def validate_status(self, value):
        instance = getattr(self, 'instance', None)
        if instance and not instance.can_transition_to(value):
            raise serializers.ValidationError(f"Cannot transition from {instance.status} to {value}")
        return value

    def validate(self, data):
        if 'latitude' in data and 'longitude' in data and not data.get('delivery_address'):
            latitude = data['latitude']
            longitude = data['longitude']
            cache_key = f"geocode_{latitude}_{longitude}"
            cached_address = cache.get(cache_key)
            if cached_address:
                data['delivery_address'] = cached_address
            else:
                for attempt in range(3):
                    try:
                        response = requests.get(
                            f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json",
                            headers={'User-Agent': 'MuindiMwesiApp/1.0'},
                            timeout=5
                        )
                        response.raise_for_status()
                        address = response.json().get('display_name', '')
                        data['delivery_address'] = address or f"Location at ({latitude}, {longitude})"
                        cache.set(cache_key, data['delivery_address'], timeout=86400)
                        break
                    except requests.RequestException as e:
                        logger.error(f"Geocoding attempt {attempt + 1} failed: {str(e)}")
                        if attempt < 2:
                            sleep(1)  # Wait before retrying
                        else:
                            data['delivery_address'] = f"Location at ({latitude}, {longitude})"
        if not data.get('delivery_address'):
            raise serializers.ValidationError("Delivery address is required")
        return data

    def update(self, instance, validated_data):
        new_status = validated_data.get('status', instance.status)
        if new_status != instance.status:
            instance.update_status(new_status)
        for attr, value in validated_data.items():
            if attr != 'status':
                setattr(instance, attr, value)
        instance.save()
        return instance
    

class RouteOptimizationSerializer(serializers.Serializer):
    start_location = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2
    )  # [lat, lng]
    delivery_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1
    )  # [id1, id2, ...]
    optimized_route = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
        required=False
    )  # [[lat, lng], ...]

    def validate_delivery_ids(self, value):
        """
        Ensure delivery IDs exist and belong to the requesting delivery person.
        """
        user = self.context['request'].user
        deliveries = Delivery.objects.filter(id__in=value, delivery_person=user)
        if len(deliveries) != len(value):
            raise serializers.ValidationError("Some delivery IDs are invalid or not assigned to you.")
        return value