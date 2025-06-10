from rest_framework import serializers
from .models import Category, Product
from cloudinary.uploader import upload
from cloudinary import CloudinaryImage

class CategorySerializer(serializers.ModelSerializer):
    image = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'image', 'created_at']

    def get_image(self, obj):
        if obj.image:
            # Build Cloudinary URL from public_id
            return CloudinaryImage(str(obj.image)).build_url()
        return None

    def validate_name(self, value):
        if Category.objects.filter(name__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['image'] = self.get_image(instance)
        return representation

    def update(self, instance, validated_data):
        if 'image' in validated_data:
            image_file = validated_data.pop('image')
            if image_file:
                upload_result = upload(image_file)
                instance.image = upload_result['public_id']
            else:
                instance.image = None
        return super().update(instance, validated_data)

class ProductSerializer(serializers.ModelSerializer):
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
            # Build Cloudinary URL from public_id
            return CloudinaryImage(str(obj.image)).build_url()
        return None

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['category'] = CategorySerializer(instance.category).data
        representation['image'] = self.get_image(instance)
        return representation

    def update(self, instance, validated_data):
        if 'image' in validated_data:
            image_file = validated_data.pop('image')
            if image_file:
                upload_result = upload(image_file)
                instance.image = upload_result['public_id']
            else:
                instance.image = None
        return super().update(instance, validated_data)