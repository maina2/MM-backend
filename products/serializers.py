from rest_framework import serializers
from .models import Category, Product

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


lass ProductSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    image = serializers.ImageField(required=False, allow_null=True)  
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
        # Ensure image is represented as the Cloudinary URL
        representation['image'] = self.get_image(instance)
        return representation

    def update(self, instance, validated_data):
        # Handle image upload to Cloudinary if provided
        if 'image' in validated_data:
            image_file = validated_data.pop('image')
            if image_file:
                # Upload to Cloudinary
                upload_result = upload(image_file)
                instance.image = upload_result['public_id']  
            else:
                instance.image = None  
        return super().update(instance, validated_data)