from rest_framework import serializers
import requests
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
        queryset=CustomUser.objects.filter(is_delivery_person=True),
        source='delivery_person',
        write_only=True,
        required=False
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
        read_only_fields = ['status', 'created_at', 'updated_at']

    def validate_order(self, order):
        """Ensure the order is paid and in 'processing' status."""
        if not hasattr(order, 'payment') or order.payment.status != 'successful':
            raise serializers.ValidationError("Order must have a successful payment")
        if order.status != 'processing':
            raise serializers.ValidationError("Order must be in 'processing' status")
        return order

    def validate_latitude(self, value):
        """Validate latitude range."""
        if value is not None and (value < -90 or value > 90):
            raise serializers.ValidationError("Latitude must be between -90 and 90")
        return value

    def validate_longitude(self, value):
        """Validate longitude range."""
        if value is not None and (value < -180 or value > 180):
            raise serializers.ValidationError("Longitude must be between -180 and 180")
        return value

    def validate(self, data):
        """Perform reverse geocoding to populate delivery_address if latitude and longitude are provided."""
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        if latitude is not None and longitude is not None and not data.get('delivery_address'):
            try:
                response = requests.get(
                    f"https://nominatim.openstreetmap.org/reverse?lat={latitude}&lon={longitude}&format=json",
                    headers={'User-Agent': 'YourAppName/1.0'},
                    timeout=5
                )
                response.raise_for_status()
                address = response.json().get('display_name', '')
                if not address:
                    # Fallback if no address is found
                    data['delivery_address'] = f"Location at ({latitude}, {longitude})"
                else:
                    data['delivery_address'] = address
            except requests.RequestException as e:
                # Fallback if reverse geocoding fails
                data['delivery_address'] = f"Location at ({latitude}, {longitude})"
        return data