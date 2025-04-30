from django.urls import path
from .views import (
    CategoryListView, CategoryDetailView, ProductListView, ProductDetailView,
    BulkCategoryCreateView, BulkBranchCreateView, BulkProductCreateView
)

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('categories/<int:id>/', CategoryDetailView.as_view(), name='category-detail'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
    path('bulk-categories/', BulkCategoryCreateView.as_view(), name='bulk-category-create'),
    path('bulk-branches/', BulkBranchCreateView.as_view(), name='bulk-branch-create'),
    path('bulk-products/', BulkProductCreateView.as_view(), name='bulk-product-create'),
]