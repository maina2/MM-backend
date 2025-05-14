from rest_framework import status
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from products.permissions import IsAdminUser
from .models import Order
from .serializers import OrderSerializer
import logging
from django.db import transaction
from orders.models import Order, OrderItem
from orders.serializers import OrderSerializer
from delivery.serializers import DeliverySerializer
from rest_framework.views import APIView
from payment.models import Payment  # Import Payment model
from payment.services import MpesaService
from django.conf import settings


logger = logging.getLogger(__name__)


class CheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        try:
            user = request.user
            data = request.data

            # Step 1: Validate cart items
            cart_items = data.get('cart_items', [])
            if not cart_items:
                return Response({"error": "Cart is empty"}, status=status.HTTP_400_BAD_REQUEST)

            # Calculate total amount
            total_amount = 0
            for item in cart_items:
                price = float(item['product']['price'])
                quantity = int(item['quantity'])
                total_amount += price * quantity

            # Step 2: Create the order
            order_data = {
                'customer': user,
                'total_amount': str(total_amount),
                'status': 'pending',
                'payment_status': 'unpaid',  # Initial status
            }
            order = Order.objects.create(**order_data)
            logger.info(f"Order created: ID {order.id} for user {user.username}")

            # Step 3: Add order items
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product_id=item['product']['id'],
                    quantity=item['quantity'],
                    price=item['product']['price']
                )

            # Step 4: Initiate M-Pesa payment using MpesaService
            phone_number = data.get('phone_number')
            if not phone_number:
                return Response({"error": "Phone number is required for payment"}, status=status.HTTP_400_BAD_REQUEST)

            # Create a Payment record
            payment = Payment.objects.create(
                order=order,
                amount=total_amount,
                phone_number=phone_number,
                status='pending'
            )
            logger.info(f"Payment record created: ID {payment.id} for Order {order.id}")

            # Initiate STK push
            mpesa_service = MpesaService()
            callback_url = getattr(settings, 'MPESA_CALLBACK_URL', None)
            if not callback_url:
                logger.error("MPESA_CALLBACK_URL not configured in settings")
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
                    logger.info(f"M-Pesa payment initiated, CheckoutRequestID: {payment.checkout_request_id}")
                else:
                    error_desc = response.get('ResponseDescription', 'Unknown error')
                    logger.error(f"M-Pesa responded with error: {error_desc}")
                    payment.status = 'failed'
                    payment.error_message = error_desc
                    payment.save()
                    order.status = 'cancelled'
                    order.payment_status = 'failed'
                    order.save()
                    return Response(
                        {"error": f"Failed to initiate M-Pesa payment: {error_desc}", "details": response},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            except Exception as mpesa_error:
                error_message = str(mpesa_error)
                logger.error(f"M-Pesa request failed: {error_message}")
                payment.status = 'failed'
                payment.error_message = f"M-Pesa request error: {error_message}"
                payment.save()
                order.status = 'cancelled'
                order.payment_status = 'failed'
                order.save()
                return Response(
                    {"error": "Failed to connect to M-Pesa service", "details": error_message},
                    status=status.HTTP_502_BAD_GATEWAY
                )

            # Step 5: Create the delivery
            delivery_data = {
                'order': order,
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
            }
            delivery_serializer = DeliverySerializer(data=delivery_data)
            delivery_serializer.is_valid(raise_exception=True)
            delivery = delivery_serializer.save()
            logger.info(f"Delivery created: ID {delivery.id} for Order {order.id}")

            # Step 6: Serialize the response
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
        
class PaymentCallbackView(GenericAPIView):
    def post(self, request, *args, **kwargs):
        try:
            logger.debug(f"Received M-Pesa callback: {request.data}")
            
            body = request.data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')

            logger.info(f"Processing callback with CheckoutRequestID: {checkout_request_id}, Result: {result_code}")

            try:
                payment = Payment.objects.get(checkout_request_id=checkout_request_id)
                logger.info(f"Found payment: {payment.id} for order: {payment.order.id}")
            except Payment.DoesNotExist:
                logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")
                return Response(
                    {"detail": "Payment not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            if result_code == 0:
                payment.status = 'successful'
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                
                # Log all metadata for debugging
                logger.debug(f"Callback metadata: {callback_metadata}")
                
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        payment.transaction_id = item.get('Value')
                        logger.info(f"Found transaction ID: {payment.transaction_id}")
                        break
            else:
                payment.status = 'failed' if result_code == 1032 else 'cancelled'
                payment.error_message = result_desc
                logger.warning(f"Payment failed/cancelled: {result_desc}")

            payment.save()
            payment.sync_order_status()  # Sync with Order
            logger.info(f"Updated payment status to: {payment.status}")
            return Response({"ResultDesc": "Callback received successfully"}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Failed to process callback: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"detail": f"Failed to process callback: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class OrderListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    serializer_class = OrderSerializer
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Order.objects.all()
        return Order.objects.filter(customer=user)

    def get(self, request, *args, **kwargs):
        try:
            return self.list(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"Failed to fetch orders: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                order = serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(
                {"detail": "Invalid order data", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to create order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OrderDetailView(RetrieveUpdateAPIView):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Order.objects.all()
        return Order.objects.filter(customer=user)

    def get(self, request, *args, **kwargs):
        try:
            return self.retrieve(request, *args, **kwargs)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to fetch order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, *args, **kwargs):
        try:
            # Restrict updates to status and payment_status for non-admins
            if not request.user.is_admin:
                allowed_fields = {'status', 'payment_status'}
                if set(request.data.keys()) - allowed_fields:
                    return Response(
                        {"detail": "Only status and payment_status can be updated"},
                        status=status.HTTP_403_FORBIDDEN
                    )
            return self.partial_update(request, *args, **kwargs)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to update order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )