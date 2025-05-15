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
from .models import Category, Branch, Product
from .serializers import CategorySerializer, BranchSerializer, ProductSerializer
from .permissions import IsAdminUser
from .pagination import ProductPagination
from rest_framework import viewsets

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
class ProductSearchView(APIView):
    pagination_class = ProductPagination

    def get(self, request, *args, **kwargs):
        try:
            # Get query parameters
            query = request.query_params.get('q', '').strip()
            category_id = request.query_params.get('category', None)
            min_price = request.query_params.get('min_price', None)
            max_price = request.query_params.get('max_price', None)
            sort_by = request.query_params.get('sort_by', 'name')  # Default to name

            # Validate sort_by
            valid_sorts = ['name', '-name', 'price', '-price']
            if sort_by not in valid_sorts:
                return Response(
                    {"error": "Invalid sort_by. Use 'name', '-name', 'price', or '-price'."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Start with in-stock products
            queryset = Product.objects.filter(stock__gt=0)

            # Apply search if query is provided
            if query:
                # Use PostgreSQL full-text search
                search_query = SearchQuery(query)
                queryset = queryset.annotate(
                    search=SearchVector('name', 'description'),
                    rank=SearchRank(SearchVector('name', 'description'), search_query)
                ).filter(search=search_query).order_by('-rank')
            else:
                # If no query, order by sort_by
                queryset = queryset.order_by(sort_by)

            # Apply filters
            if category_id:
                try:
                    queryset = queryset.filter(category__id=int(category_id))
                except ValueError:
                    return Response(
                        {"error": "Invalid category ID."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            if min_price:
                try:
                    queryset = queryset.filter(price__gte=float(min_price))
                except ValueError:
                    return Response(
                        {"error": "Invalid min_price."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            if max_price:
                try:
                    queryset = queryset.filter(price__lte=float(max_price))
                except ValueError:
                    return Response(
                        {"error": "Invalid max_price."},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Apply sorting if no search query (search uses rank)
            if not query:
                queryset = queryset.order_by(sort_by)

            # Paginate results
            page = self.paginate_queryset(queryset, request)
            if page is not None:
                serializer = ProductSerializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            # Non-paginated response (rare)
            serializer = ProductSerializer(queryset, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Search failed: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def paginate_queryset(self, queryset, request):
        if self.pagination_class is None:
            return None
        return self.pagination_class().paginate_queryset(queryset, request, view=self)

    def get_paginated_response(self, data):
        assert self.pagination_class is not None
        return self.pagination_class().get_paginated_response(data)
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