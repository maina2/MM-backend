from rest_framework import serializers
from .models import Payment
from orders.serializers import OrderSerializer
from orders.models import Order
class PaymentSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only=True)
    order_id = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(), source='order', write_only=True
    )

    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'order_id', 'amount', 'phone_number', 'status',
            'transaction_id', 'checkout_request_id', 'created_at', 'updated_at'
        ]
        read_only_fields = ['amount', 'status', 'transaction_id', 'checkout_request_id', 'created_at', 'updated_at']