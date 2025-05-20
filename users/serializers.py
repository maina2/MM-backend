# users/serializers.py
from rest_framework import serializers
from .models import CustomUser

class CustomUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'phone_number', 'role']
        read_only_fields = ['id', 'role']

class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['email', 'phone_number']

class AdminUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'phone_number', 'role', 'password', 'is_active']
        read_only_fields = ['id']

    def validate_role(self, value):
        allowed_roles = ['customer', 'delivery', 'admin']
        if value not in allowed_roles:
            raise serializers.ValidationError(f"Role must be one of {allowed_roles}")
        return value

    def validate_email(self, value):
        if CustomUser.objects.exclude(pk=self.instance.pk if self.instance else None).filter(email=value).exists():
            raise serializers.ValidationError("Email is already in use")
        return value

    def validate_username(self, value):
        if CustomUser.objects.exclude(pk=self.instance.pk if self.instance else None).filter(username=value).exists():
            raise serializers.ValidationError("Username is already in use")
        return value

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user

    def update(self, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(self.instance, attr, value)
        if password:
            self.instance.set_password(password)
        self.instance.save()
        return self.instance