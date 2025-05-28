from rest_framework import serializers
from .models import Order, OrderItem, Branch
from products.serializers import ProductSerializer
from products.models import Product


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'city']
        read_only_fields = ['id']


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
    request_id = serializers.CharField(read_only=True)
    branch = serializers.StringRelatedField(read_only=True)
    branch_id = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.filter(is_active=True), source='branch', write_only=True, required=True
    )

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'total_amount', 'status', 'payment_status',
            'payment_phone_number', 'created_at', 'updated_at', 'items', 'request_id', 'branch', 'branch_id'
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
        branch = validated_data.pop('branch')  # Extract branch from branch_id
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