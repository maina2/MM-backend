from django.core.exceptions import ValidationError
from products.models import Product

def validate_stock(items_data):
    """
    Validate stock availability for a list of items.
    Args:
        items_data: List of dicts with 'product' and 'quantity'.
    Raises:
        ValidationError: If stock is insufficient.
    """
    for item in items_data:
        product = item['product']
        quantity = item['quantity']
        if quantity > product.stock:
            raise ValidationError(
                f"Insufficient stock for {product.name}. Available: {product.stock}, Requested: {quantity}"
            )