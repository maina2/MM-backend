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
import requests
import base64
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class MpesaService:
    def __init__(self):
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        self.base_url = "https://sandbox.safaricom.co.ke"  # Use "https://api.safaricom.co.ke" for production
        self.access_token = self.get_access_token()

    def get_access_token(self):
        url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        credentials = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()
        headers = {
            "Authorization": f"Basic {credentials}"
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("access_token")

    def generate_password(self, timestamp):
        data_to_encode = f"{self.shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(data_to_encode.encode()).decode()

    def stk_push(self, phone_number, amount, account_reference, transaction_desc, callback_url):
        url = f"{self.base_url}/mpesa/stkpush/v1/processrequest"
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        password = self.generate_password(timestamp)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": self.shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()

class PaymentListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    serializer_class = PaymentSerializer
    mpesa_service = MpesaService()

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
            phone_number = phone_number.strip()
            if phone_number.startswith('+'):
                phone_number = phone_number[1:]
            if not phone_number.startswith('254') or len(phone_number) != 12 or not phone_number.isdigit():
                return Response(
                    {"error": "Invalid phone number. Use format 2547XXXXXXXXX"},
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

            payment = Payment.objects.create(
                order=order,
                amount=order.total_amount,
                phone_number=phone_number,
                status='pending'
            )

            callback_url = "https://39d0-102-217-64-46.ngrok-free.app/api/payment/callback/"
            response = self.mpesa_service.stk_push(
                phone_number=phone_number,
                amount=int(order.total_amount),
                account_reference=f"Order-{order.id}",
                transaction_desc=f"Payment for Order {order.id}",
                callback_url=callback_url
            )

            if response.get('ResponseCode') == '0':
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

            logger.info(f"Received callback with CheckoutRequestID: {checkout_request_id}")

            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
            logger.info(f"Found payment: {payment.id} for order: {payment.order.id}")

            if result_code == 0:
                payment.status = 'successful'
                callback_metadata = stk_callback.get('CallbackMetadata', {}).get('Item', [])
                for item in callback_metadata:
                    if item.get('Name') == 'MpesaReceiptNumber':
                        payment.transaction_id = item.get('Value')
                        break
            else:
                payment.status = 'failed' if result_code == 1032 else 'cancelled'

            payment.save()
            logger.info(f"Updated payment status to: {payment.status}")
            return Response({"ResultDesc": "Callback received successfully"}, status=status.HTTP_200_OK)

        except Payment.DoesNotExist:
            logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")
            return Response(
                {"error": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to process callback: {str(e)}")
            return Response(
                {"error": f"Failed to process callback: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )