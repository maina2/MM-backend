from rest_framework import serializers
from .models import Order, OrderItem
from products.serializers import ProductSerializer
from products.models import Product

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), source='product', write_only=True
    )

    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'product_id', 'quantity', 'price']
        read_only_fields = ['price']

    def validate(self, data):
        product = data['product']
        quantity = data['quantity']
        if quantity <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero.")
        if quantity > product.stock:
            raise serializers.ValidationError(
                f"Insufficient stock for {product.name}. Available: {product.stock}, Requested: {quantity}"
            )
        return data

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    customer = serializers.StringRelatedField(read_only=True)
    request_id = serializers.CharField(read_only=True)  # Changed to read_only

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'total_amount', 'status', 'payment_status',
            'payment_phone_number', 'created_at', 'updated_at', 'items', 'request_id'
        ]
        read_only_fields = ['total_amount', 'created_at', 'updated_at', 'payment_status', 'request_id']

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError("Order must include at least one item.")
        return value

    def validate_payment_phone_number(self, value):
        if value:
            value = value.strip()
            if value.startswith('2547') and len(value) == 12:
                value = f'+{value}'
            elif not (value.startswith('+2547') and len(value) == 13):
                raise serializers.ValidationError("Phone number must be in the format +2547XXXXXXXX or 2547XXXXXXXX.")
            return value
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        order = Order.objects.create(
            customer=self.context['request'].user,
            **validated_data
        )
        total_amount = 0
        for item_data in items_data:
            product = item_data['product']
            quantity = item_data['quantity']
            price = product.price
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=price
            )
            product.stock -= quantity
            product.save()
            total_amount += price * quantity
        order.total_amount = total_amount
        order.save()
        return order