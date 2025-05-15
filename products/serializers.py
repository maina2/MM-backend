# products/serializers.py
from rest_framework import serializers
from .models import Category, Branch, Product

class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'created_at']

    def get_image(self, obj):
        if obj.image:
            full_url = obj.image.url
            return full_url
        return None

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'created_at']

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'category', 'branch', 'image', 'created_at']

    def get_image(self, obj):
        if obj.image:
            return obj.image.url
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['category'] = CategorySerializer(instance.category).data
        representation['branch'] = BranchSerializer(instance.branch).data
        return representation