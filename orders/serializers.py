from rest_framework import serializers
from .models import Order, OrderItem, Branch
from products.serializers import ProductSerializer
from products.models import Product
from users.serializers import CustomUserSerializer

from rest_framework import serializers
from .models import Branch

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'city', 'latitude', 'longitude', 'is_active']
        read_only_fields = ['id']  # ID is auto-generated and read-only

    def validate_name(self, value):

        if self.instance is None and Branch.objects.filter(name=value).exists():
            raise serializers.ValidationError("A branch with this name already exists.")
        return value

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, required=False)  # Optional for updates
    customer = CustomUserSerializer(read_only=True)
    branch = serializers.StringRelatedField(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True),
        source='branch',
        write_only=True,
        required=False  # Optional for updates
    )

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'total_amount', 'status', 'payment_status',
            'payment_phone_number', 'created_at', 'updated_at', 'items',
            'request_id', 'branch', 'branch_id'
        ]
        read_only_fields = ['total_amount', 'created_at', 'updated_at', 'payment_status', 'request_id']

    def validate_items(self, value):
        if value and not value:
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
        items_data = validated_data.pop('items', [])
        branch = validated_data.pop('branch', None)
        if not branch:
            raise serializers.ValidationError({"branch_id": "This field is required for creating an order."})
        order = Order.objects.create(
            customer=self.context['request'].user,
            branch=branch,
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

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        branch = validated_data.pop('branch', None)

        # Update scalar fields
        instance.status = validated_data.get('status', instance.status)
        instance.payment_phone_number = validated_data.get('payment_phone_number', instance.payment_phone_number)
        if branch:
            instance.branch = branch

        # Handle items if provided
        if items_data is not None:
            instance.items.all().delete()
            total_amount = 0
            for item_data in items_data:
                product = item_data['product']
                quantity = item_data['quantity']
                price = product.price
                OrderItem.objects.create(
                    order=instance,
                    product=product,
                    quantity=quantity,
                    price=price
                )
                product.stock -= quantity
                product.save()
                total_amount += price * quantity
            instance.total_amount = total_amount

        instance.save()
        return instance
class CartItemSerializer(serializers.Serializer):
    product = serializers.DictField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product(self, value):
        product_id = value.get('id')
        price = value.get('price')
        if not product_id or not price:
            raise serializers.ValidationError("Product must include 'id' and 'price'.")
        try:
            product = Product.objects.get(id=product_id)
            if float(price) != float(product.price):
                raise serializers.ValidationError("Product price does not match current price.")
        except Product.DoesNotExist:
            raise serializers.ValidationError(f"Product with id {product_id} does not exist.")
        return value


class CheckoutSerializer(serializers.Serializer):
    cart_items = serializers.ListField(child=CartItemSerializer(), min_length=1)
    phone_number = serializers.CharField(max_length=15)
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    branch_id = serializers.IntegerField()  

    def validate_phone_number(self, value):
        value = value.strip()
        if value.startswith('2547') and len(value) == 12:
            value = f'+{value}'
        elif not (value.startswith('+2547') and len(value) == 13):
            raise serializers.ValidationError("Phone number must be in the format +2547XXXXXXXX or 2547XXXXXXXX.")
        return value

    def validate_cart_items(self, value):
        if not value:
            raise serializers.ValidationError("Cart cannot be empty.")
        return value