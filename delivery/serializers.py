from rest_framework import serializers
from .models import Delivery
from orders.serializers import OrderSerializer
from users.serializers import CustomUserSerializer

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
    latitude = serializers.FloatField(required=False, allow_null=True)  # Add latitude
    longitude = serializers.FloatField(required=False, allow_null=True)  # Add longitude

    class Meta:
        model = Delivery
        fields = [
            'id', 'order', 'order_id', 'delivery_person', 'delivery_person_id',
            'status', 'delivery_address', 'latitude', 'longitude',  # Add new fields
            'estimated_delivery_time', 'actual_delivery_time', 'created_at', 'updated_at'
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']