from django.contrib import admin
from django.utils.html import format_html
from .models import Category, Branch, Product

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'image_preview', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)
    fields = ('name', 'description', 'image', 'created_at')
    readonly_fields = ('created_at',)

    def image_preview(self, obj):
        # Safety check: Ensure obj has an image attribute and it's not None
        if hasattr(obj, 'image') and obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = 'Image'

@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'created_at')
    search_fields = ('name', 'address')
    list_filter = ('created_at',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'branch', 'category', 'price', 'stock', 'image_preview', 'created_at')
    search_fields = ('name', 'description')
    list_filter = ('branch', 'category', 'created_at')
    list_per_page = 25
    fields = ('name', 'description', 'price', 'stock', 'category', 'branch', 'image', 'created_at')
    readonly_fields = ('created_at',)

    def image_preview(self, obj):
        # Safety check: Ensure obj has an image attribute and it's not None
        if hasattr(obj, 'image') and obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = 'Image'