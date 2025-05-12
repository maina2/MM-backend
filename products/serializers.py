from rest_framework import serializers
from .models import Category, Branch, Product

from rest_framework import serializers
from .models import Category

class CategorySerializer(serializers.ModelSerializer):
    image = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'created_at']

    def get_image(self, obj):
        if obj.image:
            full_url = obj.image.url
            print(f"Category: {obj.name}, Public ID: {obj.image}, Full URL: {full_url}")
            return full_url
        return None

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