from django.db import models
from django.core.validators import RegexValidator
from orders.models import Order

class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                regex=r'^\+?2547[0-9]{8}$',
                message='Phone number must be in the format +2547XXXXXXXX or 2547XXXXXXXX.'
            )
        ]
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('successful', 'Successful'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for Order {self.order.id} - Status: {self.status}"

    def clean(self):
        """Normalize phone_number to include + prefix."""
        if self.phone_number and self.phone_number.startswith('2547'):
            self.phone_number = f'+{self.phone_number}'

    def save(self, *args, **kwargs):
        """Ensure clean is called before saving."""
        self.clean()
        super().save(*args, **kwargs)

    def sync_order_status(self):
        """Sync payment status with Order.payment_status and Order.status."""
        if self.status == 'successful':
            self.order.payment_status = 'paid'
            if self.order.status == 'pending':
                self.order.status = 'processing'
        elif self.status in ('failed', 'cancelled'):
            self.order.payment_status = 'failed' if self.status == 'failed' else 'unpaid'
        self.order.save()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['checkout_request_id']),
            models.Index(fields=['status']),
        ]