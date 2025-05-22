from django.db import models
from cloudinary.models import CloudinaryField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image = CloudinaryField('image', blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Categories'

class Branch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']

class Product(models.Model):
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField()
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='products', null=True, blank=True)
    image = CloudinaryField('image', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    search_vector = SearchVectorField(null=True, blank=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)  # e.g., 20.00 for 20%

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

    @property
    def discounted_price(self):
        return self.price * (1 - self.discount_percentage / 100) if self.discount_percentage > 0 else self.price

    class Meta:
        unique_together = ['name', 'branch']
        ordering = ['name']
        indexes = [
            GinIndex(fields=['search_vector']),
        ]