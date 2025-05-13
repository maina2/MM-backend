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
import traceback
import logging
from .services import MpesaService

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
            logger.error(traceback.format_exc())
            return Response(
                {"detail": f"Failed to fetch payments: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        """Create new payment and initiate M-Pesa STK push."""
        try:
            # Validate and save initial payment
            serializer = self.get_serializer(data=request.data, context={'request': request})
            if not serializer.is_valid():
                logger.warning(f"Invalid payment data: {serializer.errors}")
                return Response(
                    {"detail": "Invalid payment data", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            # Create payment record
            payment = serializer.save()
            logger.info(f"Payment created for Order #{payment.order.id}: {payment.id}")
            
            # Verify settings before making M-Pesa call
            callback_url = getattr(settings, 'MPESA_CALLBACK_URL', None)
            if not callback_url:
                logger.error("MPESA_CALLBACK_URL not configured in settings")
                payment.status = 'failed'
                payment.error_message = "Payment service configuration error: Callback URL missing"
                payment.save()
                return Response(
                    {"detail": "Payment service configuration error"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Log debug information
            logger.debug(f"Initiating M-Pesa payment with: phone={payment.phone_number}, amount={payment.amount}")
            
            # Make STK push request with better error handling
            try:
                response = self.mpesa_service.stk_push(
                    phone_number=payment.phone_number,
                    amount=payment.amount,
                    account_reference=f"Order-{payment.order.id}",
                    transaction_desc=f"Payment for Order {payment.order.id}",
                    callback_url=callback_url
                )
                
                logger.debug(f"STK Push response received: {response}")
                
                if response.get('ResponseCode') == '0':
                    payment.checkout_request_id = response.get('CheckoutRequestID')
                    payment.save()
                    logger.info(f"M-Pesa payment initiated, CheckoutRequestID: {payment.checkout_request_id}")
                    return Response(
                        serializer.data,
                        status=status.HTTP_202_ACCEPTED
                    )
                else:
                    # M-Pesa responded but with an error
                    error_desc = response.get('ResponseDescription', 'Unknown error')
                    logger.error(f"M-Pesa responded with error: {error_desc}")
                    payment.status = 'failed'
                    payment.error_message = error_desc
                    payment.save()
                    return Response(
                        {"detail": f"Failed to initiate M-Pesa payment: {error_desc}", "errors": response},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                    
            except Exception as mpesa_error:
                # Handle M-Pesa request errors
                error_message = str(mpesa_error)
                logger.error(f"M-Pesa request failed: {error_message}")
                logger.error(traceback.format_exc())
                
                # Update payment with error
                payment.status = 'failed'
                payment.error_message = f"M-Pesa request error: {error_message}"
                payment.save()
                
                return Response(
                    {
                        "detail": "Failed to connect to M-Pesa service",
                        "error": error_message
                    },
                    status=status.HTTP_502_BAD_GATEWAY
                )
                
        except Order.DoesNotExist:
            logger.error("Order not found")
            return Response(
                {"detail": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            # Handle unexpected errors
            logger.error(f"Unexpected error in payment creation: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"detail": f"Failed to create payment: {str(e)}", "error_type": type(e).__name__},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

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
            logger.error(traceback.format_exc())
            return Response(
                {"detail": f"Failed to fetch payment status: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )