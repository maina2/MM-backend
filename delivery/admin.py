# delivery/admin.py
from django.contrib import admin
from .models import Delivery

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'delivery_person', 'status', 'delivery_address', 'estimated_delivery_time', 'created_at')
    search_fields = ('order__id', 'delivery_person__username', 'delivery_address')
    list_filter = ('status', 'created_at')
    list_editable = ('status', 'delivery_person')
    readonly_fields = ('created_at', 'updated_at', 'actual_delivery_time')
    fields = ('order', 'delivery_person', 'status', 'delivery_address', 'latitude', 'longitude', 'estimated_delivery_time', 'actual_delivery_time', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    list_per_page = 25
    actions = ['mark_as_in_transit', 'mark_as_delivered']

    def mark_as_in_transit(self, request, queryset):
        for delivery in queryset:
            try:
                delivery.update_status('in_transit')
            except ValueError as e:
                self.message_user(request, f"Error for Delivery {delivery.id}: {str(e)}", level='error')
        self.message_user(request, "Selected deliveries marked as in transit.")
    mark_as_in_transit.short_description = "Mark as In Transit"

    def mark_as_delivered(self, request, queryset):
        for delivery in queryset:
            try:
                delivery.update_status('delivered')
            except ValueError as e:
                self.message_user(request, f"Error for Delivery {delivery.id}: {str(e)}", level='error')
        self.message_user(request, "Selected deliveries marked as delivered.")
    mark_as_delivered.short_description = "Mark as Delivered"

    def save_model(self, request, obj, form, change):
        if 'status' in form.changed_data:
            try:
                obj.update_status(obj.status)
            except ValueError as e:
                self.message_user(request, f"Error: {str(e)}", level='error')
                return
        super().save_model(request, obj, form, change)