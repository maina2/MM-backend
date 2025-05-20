# delivery/models.py
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from datetime import timedelta
from orders.models import Order
from users.models import CustomUser  # Adjust 'users' to your app name (e.g., 'accounts')

def default_estimated_delivery_time():
    """Return the default estimated delivery time (2 days from now)."""
    return timezone.now() + timedelta(days=2)

class Delivery(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='delivery')
    delivery_person = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'delivery'}  # Updated to use role
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_transit', 'In Transit'),
            ('delivered', 'Delivered'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    delivery_address = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)]
    )
    longitude = models.FloatField(
        null=True, blank=True,
        validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)]
    )
    estimated_delivery_time = models.DateTimeField(
        null=True, blank=True,
        default=default_estimated_delivery_time
    )
    actual_delivery_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Delivery for Order {self.order.id} - Status: {self.status}"

    def can_transition_to(self, new_status):
        """Define valid status transitions."""
        transitions = {
            'pending': ['in_transit', 'cancelled'],
            'in_transit': ['delivered', 'cancelled'],
            'delivered': [],
            'cancelled': []
        }
        return new_status in transitions.get(self.status, [])

    def update_status(self, new_status):
        """Update status with transition validation."""
        if not self.can_transition_to(new_status):
            raise ValueError(f"Cannot transition from {self.status} to {new_status}")
        self.status = new_status
        if new_status == 'delivered':
            self.actual_delivery_time = timezone.now()
        self.save()

    class Meta:
        ordering = ['-created_at']