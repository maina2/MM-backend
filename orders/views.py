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
from django.utils import timezone
from django.db import transaction
from orders.models import Order, OrderItem
from delivery.models import Delivery
from orders.serializers import OrderSerializer
from delivery.serializers import DeliverySerializer
from users.models import CustomUser
from rest_framework.views import APIView

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
                'payment_status': 'pending',
                'payment_phone_number': data.get('phone_number'),
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

            # Step 4: Initiate payment (Africa's Talking M-Pesa)
            phone_number = data.get('phone_number')
            if not phone_number:
                return Response({"error": "Phone number is required for payment"}, status=status.HTTP_400_BAD_REQUEST)

            payment_response = self.initiate_mpesa_payment(
                phone_number=phone_number,
                amount=total_amount,
                order_id=order.id
            )
            if payment_response.get('status') != 'success':
                order.status = 'cancelled'
                order.save()
                return Response({"error": "Payment initiation failed", "details": payment_response.get('error')}, status=status.HTTP_400_BAD_REQUEST)

            # Update order with payment details
            order.payment_status = 'pending'  # Will be updated via callback
            order.request_id = payment_response.get('request_id')
            order.status = 'processing'
            order.save()

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
                "payment_status": "pending",
                "message": "Checkout initiated. Please complete the payment on your phone."
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Checkout failed for user {request.user.username}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def initiate_mpesa_payment(self, phone_number, amount, order_id):
        # Africa's Talking M-Pesa STK Push
        import africastalking

        # Initialize Africa's Talking with your credentials
        africastalking.initialize(
            username='YOUR_AT_USERNAME',  # Replace with your Africa's Talking username
            api_key='YOUR_AT_API_KEY'     # Replace with your Africa's Talking API key
        )
        payment = africastalking.Payment

        try:
            # Format phone number (e.g., +254712345678)
            if not phone_number.startswith('+'):
                phone_number = '+254' + phone_number.lstrip('0')

            # Initiate STK push
            response = payment.mobile_checkout(
                product_name='YOUR_PRODUCT_NAME',  # Replace with your Africa's Talking product name
                phone_number=phone_number,
                currency_code='KES',
                amount=amount,
                metadata={'order_id': str(order_id)}
            )
            logger.info(f"M-Pesa payment initiated for order {order_id}: {response}")
            return {"status": "success", "request_id": response['transactionId']}

        except Exception as e:
            logger.error(f"M-Pesa payment initiation failed for order {order_id}: {str(e)}")
            return {"status": "failed", "error": str(e)}
        

class PaymentCallbackView(APIView):
    def post(self, request):
        try:
            data = request.data
            logger.info(f"Payment callback received: {data}")

            # Extract payment details
            transaction_id = data.get('transactionId')
            status = data.get('status')  # e.g., "Success" or "Failed"
            order_id = data.get('metadata', {}).get('order_id')

            if not order_id or not transaction_id:
                return Response({"error": "Invalid callback data"}, status=status.HTTP_400_BAD_REQUEST)

            # Update the order
            order = Order.objects.get(id=order_id)
            if status == "Success":
                order.payment_status = 'successful'
                order.status = 'processing'
            else:
                order.payment_status = 'failed'
                order.status = 'cancelled'
            order.save()

            logger.info(f"Order {order_id} payment updated: {order.payment_status}")
            return Response({"status": "success"}, status=status.HTTP_200_OK)

        except Order.DoesNotExist:
            logger.error(f"Order {order_id} not found in payment callback")
            return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Payment callback processing failed: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
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