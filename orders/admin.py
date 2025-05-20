# orders/admin.py
from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')
    can_delete = False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'total_amount', 'status', 'payment_status', 'payment_phone_number', 'created_at')
    search_fields = ('customer__username', 'customer__email', 'request_id')
    list_filter = ('status', 'payment_status', 'created_at')
    list_editable = ('status', 'payment_status')
    readonly_fields = ('created_at', 'updated_at', 'request_id')
    fields = ('customer', 'total_amount', 'status', 'payment_status', 'payment_phone_number', 'request_id', 'created_at', 'updated_at')
    inlines = [OrderItemInline]
    ordering = ('-created_at',)
    list_per_page = 25
    actions = ['mark_as_shipped', 'mark_as_delivered', 'mark_as_paid']

    def mark_as_shipped(self, request, queryset):
        queryset.update(status='shipped')
        self.message_user(request, "Selected orders marked as shipped.")
    mark_as_shipped.short_description = "Mark as Shipped"

    def mark_as_delivered(self, request, queryset):
        queryset.update(status='delivered')
        self.message_user(request, "Selected orders marked as delivered.")
    mark_as_delivered.short_description = "Mark as Delivered"

    def mark_as_paid(self, request, queryset):
        queryset.update(payment_status='paid')
        self.message_user(request, "Selected orders marked as paid.")
    mark_as_paid.short_description = "Mark as Paid"

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'quantity', 'price')
    search_fields = ('order__id', 'product__name')
    list_filter = ('order__status',)
    readonly_fields = ('order', 'product', 'quantity', 'price')
    ordering = ('order__created_at',)