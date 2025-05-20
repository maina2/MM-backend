# delivery/serializers.py
from rest_framework import serializers
import requests
from django.core.cache import cache
from .models import Delivery
from orders.serializers import OrderSerializer
from users.serializers import CustomUserSerializer
from orders.models import Order
from users.models import CustomUser

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
        if order.status != 'processing':
            raise serializers.ValidationError("Order must be in 'processing' status")
        return order

    def validate_latitude(self, value):
        if value is not None and (value < -90 or value > 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value

    def validate_longitude(self, value):
        if value is not None and (value < -180 or value > 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value

    def validate_status(self, value):
        instance = getattr(self, 'instance', None)
        if instance and not instance.can_transition_to(value):
            raise serializers.ValidationError(
                f"Cannot transition from {instance.status} to {value}"
            )
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
                except requests.RequestException as e:
                    logger.error(f"Geocoding failed: {str(e)}")
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