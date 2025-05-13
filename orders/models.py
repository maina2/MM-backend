from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from products.models import Product

User = get_user_model()

class Order(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    payment_phone_number = models.CharField(
        max_length=15,
        null=True,
        blank=True,
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
            ('processing', 'Processing'),
            ('shipped', 'Shipped'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('unpaid', 'Unpaid'),
            ('paid', 'Paid'),
            ('failed', 'Failed'),
            ('pending', 'Pending Payment')
        ],
        default='unpaid'
    )
    request_id = models.CharField(
        max_length=36,
        unique=True,
        null=True,
        blank=True,
        help_text='Unique ID for the order request to prevent duplicates.'
    )

    def __str__(self):
        return f"Order {self.id} by {self.customer.username}"

    def clean(self):
        if self.payment_phone_number and self.payment_phone_number.startswith('2547'):
            self.payment_phone_number = f'+{self.payment_phone_number}'

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def recalculate_total(self):
        total = sum(item.price * item.quantity for item in self.items.all())
        self.total_amount = total
        self.save()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['request_id']),
        ]

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.id}"

    class Meta:
        unique_together = ['order', 'product']