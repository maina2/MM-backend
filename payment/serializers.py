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
            'transaction_id', 'checkout_request_id', 'error_message', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'amount', 'status', 'transaction_id', 'checkout_request_id',
            'error_message', 'created_at', 'updated_at'
        ]

    def validate(self, data):
        order = data['order']
        phone_number = data['phone_number']
        if hasattr(order, 'payment'):
            raise serializers.ValidationError("A payment already exists for this order.")
        if order.payment_status != 'unpaid':
            raise serializers.ValidationError("Order already has a payment status.")
        # Normalize phone_number
        phone_number = phone_number.strip()
        if phone_number.startswith('2547') and len(phone_number) == 12:
            data['phone_number'] = f'+{phone_number}'
        elif not (phone_number.startswith('+2547') and len(phone_number) == 13):
            raise serializers.ValidationError("Phone number must be in the format +2547XXXXXXXX or 2547XXXXXXXX.")
        return data

    def validate_order_id(self, value):
        if value.customer != self.context['request'].user:
            raise serializers.ValidationError("You can only create payments for your own orders.")
        return value

    def create(self, validated_data):
        # Set amount from order.total_amount
        validated_data['amount'] = validated_data['order'].total_amount
        return super().create(validated_data)