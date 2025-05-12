from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin, RetrieveModelMixin, UpdateModelMixin, DestroyModelMixin
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from .models import Category, Branch, Product
from .serializers import CategorySerializer, BranchSerializer, ProductSerializer
from .permissions import IsAdminUser
from rest_framework import viewsets

# ViewSet for Categories (list only)
class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    http_method_names = ['get']  # Restrict to GET

    # Disable the retrieve action (we'll use CategoryDetailViewSet instead)
    def retrieve(self, request, *args, **kwargs):
        return Response({'error': 'Use /categories/<id>/ for details'}, status=400)

# ViewSet for Category Details (including products under a category)
class CategoryDetailViewSet(viewsets.ViewSet):
    def retrieve(self, request, pk=None):
        try:
            # Fetch the category by ID
            category = Category.objects.get(pk=pk)
            category_serializer = CategorySerializer(category)

            # Fetch products under this category
            products = Product.objects.filter(category=category)
            product_serializer = ProductSerializer(products, many=True)

            # Combine category details and its products in the response
            return Response({
                'category': category_serializer.data,
                'products': product_serializer.data
            })
        except Category.DoesNotExist:
            return Response({'error': 'Category not found'}, status=404)
class ProductListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['branch', 'category']
    pagination_class = None

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