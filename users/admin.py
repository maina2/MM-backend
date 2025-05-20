# yourapp/admin.py
from django.contrib import admin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('id', 'username', 'email', 'phone_number', 'role', 'is_active', 'date_joined')
    search_fields = ('username', 'email', 'phone_number')
    list_filter = ('role', 'is_active', 'date_joined')
    list_editable = ('role', 'is_active')
    readonly_fields = ('date_joined',)
    fields = ('username', 'email', 'phone_number', 'role', 'is_active', 'is_staff', 'groups', 'user_permissions')
    ordering = ('username',)

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        return queryset, False