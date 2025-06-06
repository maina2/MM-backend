# products/urls.py
from django.urls import path, include
from .views import (
    CategoryViewSet, CategoryDetailViewSet, ProductListView, ProductDetailView, ProductSearchView,BulkCategoryCreateView,
    BulkProductCreateView,OffersListView,AdminProductListCreateView,AdminProductDetailView,
    AdminCategoryListCreateView,AdminCategoryDetailView
)
from rest_framework.routers import DefaultRouter

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')

urlpatterns = [
    path('categories/<int:pk>/', CategoryDetailViewSet.as_view({'get': 'retrieve'}), name='category-detail'),
    path('', include(router.urls)),
    path('products/', ProductListView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/search/', ProductSearchView.as_view(), name='product-search'),
    path('products/offers/', OffersListView.as_view(), name='offers-list'),
    path('manage/products/', AdminProductListCreateView.as_view(), name='admin-product-list-create'),
    path('manage/products/<int:id>/', AdminProductDetailView.as_view(), name='admin-product-detail'),
    path('manage/categories/', AdminCategoryListCreateView.as_view(), name='admin-category-list-create'),
    path('manage/categories/<int:id>/', AdminCategoryDetailView.as_view(), name='admin-category-detail'),
    path('bulk-categories/', BulkCategoryCreateView.as_view(), name='bulk-category-create'),
    path('bulk-products/', BulkProductCreateView.as_view(), name='bulk-product-create'),
]