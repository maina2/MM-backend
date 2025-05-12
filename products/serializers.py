from rest_framework import serializers
from .models import Category, Branch, Product

class CategorySerializer(serializers.ModelSerializer):  
    image = serializers.CharField(allow_blank=True, required=False)
    class Meta:
        model = Category
        fields = ['id', 'name', 'description','image', 'created_at']

class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ['id', 'name', 'address', 'created_at']

class ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all())
    image = serializers.CharField(allow_blank=True, required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'stock', 'category', 'branch', 'image', 'created_at']

    def to_representation(self, instance):
        # Override to include nested category and branch data in responses
        representation = super().to_representation(instance)
        representation['category'] = CategorySerializer(instance.category).data
        representation['branch'] = BranchSerializer(instance.branch).data
        return representation