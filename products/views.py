# products/views.py
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin, RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.views import APIView
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.db.models import Q
from .models import Category, Product
from .serializers import CategorySerializer, BranchSerializer, ProductSerializer
from .permissions import IsAdminUser
from .pagination import ProductPagination
from rest_framework import viewsets
from rest_framework import serializers
from rest_framework import generics
from rest_framework.filters import SearchFilter


# ViewSet for Categories (list only)
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    http_method_names = ['get']
    pagination_class = None

    def retrieve(self, request, *args, **kwargs):
        return Response({'error': 'Use /categories/<id>/ for details'}, status=400)

# ViewSet for Category Details
class CategoryDetailViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk=None):
        try:
            category = Category.objects.get(pk=pk)
            category_serializer = CategorySerializer(category)
            products = Product.objects.filter(category=category)
            product_serializer = ProductSerializer(products, many=True)
            return Response({
                'category': category_serializer.data,
                'products': product_serializer.data
            })
        except Category.DoesNotExist:
            return Response({'error': 'Category not found'}, status=404)

# Product List View (updated for pagination and public access)
class ProductListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    queryset = Product.objects.filter(stock__gt=0)  # Only in-stock products
    serializer_class = ProductSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'category']
    pagination_class = ProductPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return []  # Allow public GET

    def get(self, request, *args, **kwargs):
        try:
            queryset = self.filter_queryset(self.get_queryset())
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch products: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to create product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Product Detail View
class ProductDetailView(GenericAPIView, RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    lookup_field = 'id'
    permission_classes = [IsAdminUser]

    def get(self, request, id, *args, **kwargs):
        try:
            product = get_object_or_404(Product, id=id)
            serializer = self.get_serializer(product)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def put(self, request, id, *args, **kwargs):
        try:
            product = get_object_or_404(Product, id=id)
            serializer = self.get_serializer(product, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to update product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, id, *args, **kwargs):
        try:
            product = get_object_or_404(Product, id=id)
            product.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response(
                {"error": f"Failed to delete product: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Product Search View
class ProductSearchView(GenericAPIView, ListModelMixin):
    queryset = Product.objects.filter(stock__gt=0)
    serializer_class = ProductSerializer
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['category']

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.query_params.get('q', '').strip()
        min_price = self.request.query_params.get('min_price', None)
        max_price = self.request.query_params.get('max_price', None)
        sort_by = self.request.query_params.get('sort_by', 'name')

        # Validate sort_by
        valid_sorts = ['name', '-name', 'price', '-price']
        if sort_by not in valid_sorts:
            raise serializers.ValidationError(
                "Invalid sort_by. Use 'name', '-name', 'price', or '-price'."
            )

        # Apply search if query is provided
        if query:
            search_query = SearchQuery(query)
            queryset = queryset.annotate(
                search=SearchVector('name', 'description'),
                rank=SearchRank(SearchVector('name', 'description'), search_query)
            ).filter(search=search_query).order_by('-rank')
        else:
            queryset = queryset.order_by(sort_by)

        # Apply price filters
        if min_price:
            try:
                queryset = queryset.filter(price__gte=float(min_price))
            except ValueError:
                raise serializers.ValidationError("Invalid min_price.")

        if max_price:
            try:
                queryset = queryset.filter(price__lte=float(max_price))
            except ValueError:
                raise serializers.ValidationError("Invalid max_price.")

        return queryset

    def get(self, request, *args, **kwargs):
        try:
            return self.list(request, *args, **kwargs)
        except serializers.ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"error": f"Search failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
class OffersListView(generics.ListAPIView):
    serializer_class = ProductSerializer
    pagination_class = ProductPagination

    def get_queryset(self):
        queryset = Product.objects.filter(discount_percentage__gt=0, stock__gt=0)
        # Filters
        category = self.request.query_params.get('category')
        min_discount = self.request.query_params.get('min_discount')
        max_price = self.request.query_params.get('max_price')
        sort_by = self.request.query_params.get('sort_by', '-discount_percentage')
        if category:
            queryset = queryset.filter(category_id=category)
        if min_discount:
            queryset = queryset.filter(discount_percentage__gte=min_discount)
        if max_price:
            queryset = queryset.filter(price__lte=max_price)
        # Validate sort_by
        valid_sort_fields = [
            'discount_percentage', '-discount_percentage',
            'price', '-price',
            'name', '-name'
        ]
        if sort_by not in valid_sort_fields:
            sort_by = '-discount_percentage'
        return queryset.order_by(sort_by)
    

class AdminProductListCreateView(generics.ListCreateAPIView):
    queryset = Product.objects.all().order_by("-created_at")
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]
    pagination_class = ProductPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["category", "branch"]
    search_fields = ["name", "description"]

class AdminProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]
    lookup_field = "id"


class AdminCategoryListCreateView(generics.ListCreateAPIView):
    queryset = Category.objects.all().order_by('name')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]
    pagination_class = ProductPagination
    filter_backends = [SearchFilter]
    search_fields = ['name', 'description']

class AdminCategoryDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]
    lookup_field = 'id'

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.products.exists():
            return Response(
                {"error": "Cannot delete category with associated products."},
                status=status.HTTP_400_BAD_REQUEST
            )
        return super().destroy(request, *args, **kwargs)
# New views for bulk creation
class BulkCategoryCreateView(GenericAPIView):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        try:
            # Expecting a list of category data
            if not isinstance(request.data, list):
                return Response(
                    {"error": "Expected a list of category data"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = self.get_serializer(data=request.data, many=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to create categories: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BulkBranchCreateView(GenericAPIView):
    serializer_class = BranchSerializer
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        try:
            # Expecting a list of branch data
            if not isinstance(request.data, list):
                return Response(
                    {"error": "Expected a list of branch data"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = self.get_serializer(data=request.data, many=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to create branches: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class BulkProductCreateView(GenericAPIView):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]

    def post(self, request, *args, **kwargs):
        try:
            # Expecting a list of product data
            if not isinstance(request.data, list):
                return Response(
                    {"error": "Expected a list of product data"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            serializer = self.get_serializer(data=request.data, many=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to create products: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )