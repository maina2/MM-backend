from rest_framework import serializers
from .models import Category, Branch, Product

class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'created_at']

    def get_image(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def validate_name(self, value):
        if Category.objects.filter(name__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value


class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())   
    image = serializers.SerializerMethodField()
    discounted_price = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'stock', 'category', 
            'image', 'created_at', 'discount_percentage', 'discounted_price'
        ]

    def get_image(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['category'] = CategorySerializer(instance.category).data
        return representation