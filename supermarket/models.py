from django.db import models

class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Product(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='products')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

    class Meta:
        unique_together = ['name', 'branch']  # Prevent duplicate products per branch
        ordering = ['name']

class Order(models.Model):
    customer_name = models.CharField(max_length=100)
    customer_phone = models.CharField(max_length=20)
    delivery_address = models.TextField()
    delivery_area = models.CharField(max_length=100, blank=True)  # E.g., "Embakasi"
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=[
            ('Pending', 'Pending'),
            ('Batched', 'Batched'),
            ('Delivered', 'Delivered'),
            ('Cancelled', 'Cancelled'),
        ],
        default='Pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='orders')

    def __str__(self):
        return f"Order {self.id} by {self.customer_name}"

    def save(self, *args, **kwargs):
        # Auto-set delivery_area from address (simplified)
        if not self.delivery_area and self.delivery_address:
            self.delivery_area = self.delivery_address.split(',')[0].strip()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    class Meta:
        ordering = ['product__name']

class DeliveryBatch(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='batches')
    delivery_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('Scheduled', 'Scheduled'),
            ('In Transit', 'In Transit'),
            ('Completed', 'Completed'),
        ],
        default='Scheduled'
    )
    orders = models.ManyToManyField(Order, related_name='delivery_batches')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Batch {self.id} for {self.branch.name} at {self.delivery_time}"

    class Meta:
        ordering = ['delivery_time']