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
    list_display = (
        'name',
        'branch',
        'category',
        'price',
        'discounted_price_display',
        'discount_percentage',
        'stock',
        'image_preview',
        'created_at',
    )
    search_fields = ('name', 'description')
    list_filter = ('branch', 'category', 'discount_percentage', 'created_at')
    list_per_page = 25
    fields = (
        'name',
        'description',
        'price',
        'discount_percentage',
        'stock',
        'category',
        'branch',
        'image',
        'created_at',
    )
    readonly_fields = ('created_at',)
    list_editable = ('price', 'discount_percentage', 'stock')
    actions = ['mark_as_on_offer', 'remove_offer']

    def image_preview(self, obj):
        if hasattr(obj, 'image') and obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 100px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = 'Image'

    def discounted_price_display(self, obj):
        return f"KSh {obj.discounted_price:,.2f}"
    discounted_price_display.short_description = 'Discounted Price'

    def mark_as_on_offer(self, request, queryset):
        queryset.update(discount_percentage=10.00)
        self.message_user(request, "Selected products marked as on offer with 10% discount.")
    mark_as_on_offer.short_description = "Mark selected products as on offer (10%%)"

    def remove_offer(self, request, queryset):
        queryset.update(discount_percentage=0.00)
        self.message_user(request, "Selected products' offers removed.")
    remove_offer.short_description = "Remove offer from selected products"

    def formfield_for_dbfield(self, db_field, **kwargs):
        if db_field.name == 'discount_percentage':
            kwargs['widget'] = admin.widgets.AdminTextInputWidget(attrs={
                'type': 'number',
                'step': '0.01',
                'min': '0',
                'max': '100',
                'placeholder': 'Enter percentage (e.g., 20.00)',
            })
        return super().formfield_for_dbfield(db_field, **kwargs)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'branch')