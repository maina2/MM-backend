from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from products.permissions import IsAdminUser
from orders.models import Order
from .models import Payment
from .serializers import PaymentSerializer
from django.conf import settings
from daraja.mpesa import MpesaClient

class PaymentListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    serializer_class = PaymentSerializer
    mpesa_client = MpesaClient(
        consumer_key=settings.MPESA_CONSUMER_KEY,
        consumer_secret=settings.MPESA_CONSUMER_SECRET,
        environment='sandbox'  # Use 'production' for live environment
    )

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Payment.objects.all()
        return Payment.objects.filter(order__customer=user)

    def get(self, request, *args, **kwargs):
        try:
            payments = self.get_queryset()
            serializer = self.get_serializer(payments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"error": f"Failed to fetch payments: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        try:
            order_id = request.data.get('order_id')
            phone_number = request.data.get('phone_number')
            if not phone_number:
                return Response(
                    {"error": "Phone number is required for M-Pesa payment"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            order = Order.objects.get(id=order_id)
            if order.customer != request.user:
                return Response(
                    {"error": "You can only create payments for your own orders"},
                    status=status.HTTP_403_FORBIDDEN
                )
            if hasattr(order, 'payment'):
                return Response(
                    {"error": "A payment already exists for this order"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create Payment instance
            payment = Payment.objects.create(
                order=order,
                amount=order.total_amount,
                phone_number=phone_number,
                status='pending'
            )

            # Initiate M-Pesa STK Push
            callback_url = "https://your-ngrok-url/api/payment/callback/"  # Replace with your ngrok URL
            response = self.mpesa_client.stk_push(
                phone_number=phone_number,
                amount=int(order.total_amount),  # M-Pesa API expects integer amount
                account_reference=f"Order-{order.id}",
                transaction_desc=f"Payment for Order {order.id}",
                callback_url=callback_url,
                business_shortcode=settings.MPESA_SHORTCODE,
                passkey=settings.MPESA_PASSKEY
            )

            if response.get('ResponseCode') == '0':  # Success
                payment.checkout_request_id = response.get('CheckoutRequestID')
                payment.save()
                serializer = self.get_serializer(payment)
                return Response(
                    serializer.data,
                    status=status.HTTP_202_ACCEPTED
                )
            else:
                payment.status = 'failed'
                payment.save()
                return Response(
                    {"error": "Failed to initiate M-Pesa payment", "details": response},
                    status=status.HTTP_400_BAD_REQUEST
                )

        except Order.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to create payment: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PaymentCallbackView(GenericAPIView):
    def post(self, request, *args, **kwargs):
        try:
            body = request.data.get('Body', {})
            stk_callback = body.get('stkCallback', {})
            checkout_request_id = stk_callback.get('CheckoutRequestID')
            result_code = stk_callback.get('ResultCode')
            result_desc = stk_callback.get('ResultDesc')

            payment = Payment.objects.get(checkout_request_id=checkout_request_id)

            if result_code == 0:  # Payment successful
                payment.status = 'successful'
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        payment.transaction_id = item.get('Value')
                        break
            else:  # Payment failed or cancelled
                payment.status = 'failed' if result_code == 1032 else 'cancelled'

            payment.save()
            return Response({"ResultDesc": "Callback received successfully"}, status=status.HTTP_200_OK)

        except Payment.DoesNotExist:
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to process callback: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )