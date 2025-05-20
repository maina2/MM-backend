# payments/admin.py
from django.contrib import admin
from .models import Payment

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'amount', 'phone_number', 'status', 'transaction_id', 'created_at')
    search_fields = ('order__id', 'phone_number', 'transaction_id', 'checkout_request_id')
    list_filter = ('status', 'created_at')
    list_editable = ('status',)
    readonly_fields = ('created_at', 'updated_at', 'transaction_id', 'checkout_request_id', 'error_message')
    fields = ('order', 'amount', 'phone_number', 'status', 'transaction_id', 'checkout_request_id', 'error_message', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    list_per_page = 25
    actions = ['mark_as_successful', 'mark_as_failed']

    def mark_as_successful(self, request, queryset):
        queryset.update(status='successful')
        for payment in queryset:
            payment.sync_order_status()
        self.message_user(request, "Selected payments marked as successful and order statuses updated.")
    mark_as_successful.short_description = "Mark as Successful"

    def mark_as_failed(self, request, queryset):
        queryset.update(status='failed')
        for payment in queryset:
            payment.sync_order_status()
        self.message_user(request, "Selected payments marked as failed and order statuses updated.")
    mark_as_failed.short_description = "Mark as Failed"