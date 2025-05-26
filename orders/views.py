from rest_framework import status, viewsets, generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from products.permissions import IsAdminUser
from django.db import transaction
from django.db.models import Q
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
import logging
from orders.models import Order, OrderItem, Branch
from orders.serializers import OrderSerializer, CheckoutSerializer, BranchSerializer
from delivery.serializers import DeliverySerializer
from payment.models import Payment
from payment.services import MpesaService
from django.conf import settings
import traceback

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class BranchListCreateView(generics.ListCreateAPIView):
    serializer_class = BranchSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminUser()]
        return [AllowAny()]

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_admin:
            return Branch.objects.all()
        return Branch.objects.filter(is_active=True)

class BranchDetailUpdateView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BranchSerializer

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminUser()]
        return [AllowAny()]

    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_admin:
            return Branch.objects.all()
        return Branch.objects.filter(is_active=True)

class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            user = request.user
            logger.info(f"Received checkout request from user {user.username}: {request.data}")

            # Step 1: Validate input data
            serializer = CheckoutSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Validation failed: {serializer.errors}")
                return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

            validated_data = serializer.validated_data
            cart_items = validated_data['cart_items']
            phone_number = validated_data['phone_number']
            latitude = validated_data['latitude']
            longitude = validated_data['longitude']
            branch_id = validated_data['branch_id']
            logger.info(f"Selected branch ID: {branch_id}")

            # Step 2: Validate stock
            for item in cart_items:
                product_id = item['product']['id']
                quantity = item['quantity']
                try:
                    product = OrderItem.objects.get(product_id=product_id).product
                    if quantity > product.stock:
                        raise ValueError(f"Insufficient stock for product {product.name}: {product.stock} available")
                except OrderItem.DoesNotExist:
                    logger.error(f"Product {product_id} not found")
                    return Response({"error": f"Product {product_id} not found"}, status=status.HTTP_400_BAD_REQUEST)

            # Step 3: Calculate total amount
            total_amount = sum(float(item['product']['price']) * int(item['quantity']) for item in cart_items)

            # Step 4: Create the order
            order = Order.objects.create(
                customer=user,
                total_amount=total_amount,
                status='pending',
                payment_status='pending',
                payment_phone_number=phone_number,
                branch_id=branch_id
            )
            logger.info(f"Order created: ID {order.id} for user {user.username}")

            # Step 5: Add order items
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product_id=item['product']['id'],
                    quantity=item['quantity'],
                    price=item['product']['price']
                )

            # Step 6: Initiate M-Pesa payment
            payment = Payment.objects.create(
                order=order,
                amount=total_amount,
                phone_number=phone_number,
                status='pending'
            )
            logger.info(f"Payment record created: ID {payment.id} for Order {order.id}")

            mpesa_service = MpesaService()
            callback_url = getattr(settings, 'MPESA_CALLBACK_URL', None)
            if not callback_url:
                logger.error("MPESA_CALLBACK_URL not configured")
                payment.status = 'failed'
                payment.error_message = "Payment service configuration error: Callback URL missing"
                payment.save()
                return Response(
                    {"error": "Payment service configuration error"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            try:
                response = mpesa_service.stk_push(
                    phone_number=payment.phone_number,
                    amount=payment.amount,
                    account_reference=f"Order-{order.id}",
                    transaction_desc=f"Payment for Order {order.id}",
                    callback_url=callback_url
                )

                if response.get('ResponseCode') == '0':
                    payment.checkout_request_id = response.get('CheckoutRequestID')
                    payment.save()
                    logger.info(f"M-Pesa payment initiated: {payment.checkout_request_id}")
                else:
                    error_desc = response.get('ResponseDescription', 'Unknown error')
                    logger.error(f"M-Pesa error: {error_desc}")
                    payment.status = 'failed'
                    payment.error_message = error_desc
                    payment.save()
                    order.status = 'cancelled'
                    order.payment_status = 'failed'
                    order.save()
                    return Response(
                        {"error": f"Failed to initiate M-Pesa payment: {error_desc}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            except Exception as e:
                logger.error(f"M-Pesa request failed: {str(e)}")
                payment.status = 'failed'
                payment.error_message = f"M-Pesa request error: {str(e)}"
                payment.save()
                order.status = 'cancelled'
                order.payment_status = 'failed'
                order.save()
                return Response(
                    {"error": "Failed to connect to M-Pesa service", "details": str(e)},
                    status=status.HTTP_502_BAD_GATEWAY
                )

            # Step 7: Create the delivery
            delivery_data = {
                'order_id': order.id,
                'latitude': latitude,
                'longitude': longitude,
            }
            delivery_serializer = DeliverySerializer(data=delivery_data)
            if not delivery_serializer.is_valid():
                logger.error(f"Delivery validation failed: {delivery_serializer.errors}")
                return Response({"error": delivery_serializer.errors}, status=status.HTTP_400_BAD_REQUEST)
            delivery = delivery_serializer.save()
            logger.info(f"Delivery created: ID {delivery.id} for Order {order.id}")

            # Step 8: Serialize the response
            order_serializer = OrderSerializer(order)
            return Response({
                "order": order_serializer.data,
                "delivery_id": delivery.id,
                "payment_status": payment.status,
                "message": "Checkout initiated. Please complete the payment on your phone."
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Checkout failed for user {request.user.username}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

class PaymentCallbackView(generics.GenericAPIView):
    def post(self, request, *args, **kwargs):
        try:
            logger.debug(f"Received M-Pesa callback: {request.data}")
            body = request.data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')

            logger.info(f"Processing callback: {checkout_request_id}, Result: {result_code}")

            try:
                payment = Payment.objects.get(checkout_request_id=checkout_request_id)
                logger.info(f"Found payment: {payment.id} for order: {payment.order.id}")
            except Payment.DoesNotExist:
                logger.error(f"Payment not found: {checkout_request_id}")
                return Response({"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

            if result_code == 0:
                payment.status = 'successful'
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        payment.transaction_id = item.get('Value')
                        break
            else:
                payment.status = 'failed' if result_code == 1032 else 'cancelled'
                payment.error_message = result_desc

            payment.save()
            payment.sync_order_status()
            logger.info(f"Updated payment status: {payment.status}")
            return Response({"ResultDesc": "Callback received successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Callback processing failed: {str(e)}")
            return Response({"detail": f"Failed to process callback: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_status', 'branch_id']
    search_fields = ['customer__username', 'id', 'request_id']
    ordering_fields = ['created_at', 'total_amount', 'id']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.action in ['create', 'list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.select_related('customer').prefetch_related('items__product')
        if not user.is_admin:
            return queryset.filter(customer=user)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        if not request.user.is_admin:
            serializer.validated_data['customer'] = request.user
        order = serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        if 'items' in request.data:
            instance.recalculate_total()
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)