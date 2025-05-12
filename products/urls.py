from django.urls import path,include
from .views import (
   CategoryViewSet, CategoryDetailViewSet, ProductListView, ProductDetailView,
    BulkCategoryCreateView, BulkBranchCreateView, BulkProductCreateView
)
from rest_framework.routers import DefaultRouter


# Create a router for the CategoryViewSet
router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    path('', include(router.urls)),  # Includes /categories/ and /categories/<id>/
    path('categories/<int:pk>/', CategoryDetailViewSet.as_view({'get': 'retrieve'}), name='category-detail'),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
    path('bulk-categories/', BulkCategoryCreateView.as_view(), name='bulk-category-create'),
    path('bulk-branches/', BulkBranchCreateView.as_view(), name='bulk-branch-create'),
    path('bulk-products/', BulkProductCreateView.as_view(), name='bulk-product-create'),
]