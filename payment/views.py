from rest_framework import status
from rest_framework.generics import GenericAPIView, RetrieveAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from products.permissions import IsAdminUser
from orders.models import Order
from .models import Payment
from .serializers import PaymentSerializer
from django.conf import settings
from .services import MpesaService
import logging

logger = logging.getLogger(__name__)

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class PaymentListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    serializer_class = PaymentSerializer
    pagination_class = StandardResultsSetPagination
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
            return self.list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Failed to fetch payments: {str(e)}")
            return Response(
                {"detail": f"Failed to fetch payments: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        try:
            serializer = self.get_serializer(data=request.data, context={'request': request})
            if serializer.is_valid():
                payment = serializer.save()
                callback_url = settings.MPESA_CALLBACK_URL
                response = self.mpesa_service.stk_push(
                    phone_number=payment.phone_number,
                    amount=payment.amount,
                    account_reference=f"Order-{payment.order.id}",
                    transaction_desc=f"Payment for Order {payment.order.id}",
                    callback_url=callback_url
                )

                if response.get('ResponseCode') == '0':
                    payment.checkout_request_id = response.get('CheckoutRequestID')
                    payment.save()
                    return Response(
                        serializer.data,
                        status=status.HTTP_202_ACCEPTED
                    )
                else:
                    payment.status = 'failed'
                    payment.error_message = response.get('ResponseDescription', 'Unknown error')
                    payment.save()
                    return Response(
                        {"detail": "Failed to initiate M-Pesa payment", "errors": response},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            return Response(
                {"detail": "Invalid payment data", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to create payment: {str(e)}")
            return Response(
                {"detail": f"Failed to create payment: {str(e)}"},
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
                payment.error_message = result_desc

            payment.save()
            payment.sync_order_status()  # Sync with Order
            logger.info(f"Updated payment status to: {payment.status}")
            return Response({"ResultDesc": "Callback received successfully"}, status=status.HTTP_200_OK)

        except Payment.DoesNotExist:
            logger.error(f"Payment not found for CheckoutRequestID: {checkout_request_id}")
            return Response(
                {"detail": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to process callback: {str(e)}")
            return Response(
                {"detail": f"Failed to process callback: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class PaymentStatusView(RetrieveAPIView):
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        user = self.request.user
        if user.is_admin:
            return Payment.objects.all()
        return Payment.objects.filter(order__customer=user)

    def get(self, request, *args, **kwargs):
        try:
            return self.retrieve(request, *args, **kwargs)
        except Payment.DoesNotExist:
            return Response(
                {"detail": "Payment not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to fetch payment status: {str(e)}")
            return Response(
                {"detail": f"Failed to fetch payment status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )