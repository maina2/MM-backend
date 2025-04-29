from django.contrib import admin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_admin', 'date_joined')
    search_fields = ('username', 'email', 'phone_number')
    list_filter = ('is_admin', 'date_joined')