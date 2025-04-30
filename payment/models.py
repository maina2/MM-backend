from django.db import models
from orders.models import Order

class Payment(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=15)  # Customer's phone number for M-Pesa
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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for Order {self.order.id} - Status: {self.status}"

    class Meta:
        ordering = ['-created_at']