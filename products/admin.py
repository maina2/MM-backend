from django.contrib import admin
from .models import Category, Branch, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'created_at')
    search_fields = ('name', 'address')
    list_filter = ('created_at',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'category', 'price', 'stock', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('branch', 'category', 'created_at')
    list_per_page = 25