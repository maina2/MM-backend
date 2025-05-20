# yourapp/admin.py
from django.contrib import admin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'role', 'date_joined')
    search_fields = ('username', 'email', 'phone_number')
    list_filter = ('role', 'date_joined')
    fields = ('username', 'email', 'phone_number', 'role', 'is_active', 'is_staff', 'groups', 'user_permissions')