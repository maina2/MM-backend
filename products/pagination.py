# products/pagination.py
from rest_framework.pagination import PageNumberPagination

class ProductPagination(PageNumberPagination):
    page_size = 12  # Default to 12 items per page
    page_size_query_param = 'page_size'  # Allow ?page_size=24
    max_page_size = 100  # Prevent abuse