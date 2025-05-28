from rest_framework import status, viewsets, generics
from rest_framework.generics import GenericAPIView, RetrieveUpdateAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Q
from django.conf import settings
import logging
import traceback

from products.permissions import IsAdminUser
from orders.models import Order, OrderItem, Branch
from orders.serializers import OrderSerializer, CheckoutSerializer, BranchSerializer
from delivery.serializers import DeliverySerializer
from payment.models import Payment
from payment.services import MpesaService


logger = logging.getLogger(__name__)


class BranchListView(generics.ListAPIView):
    """
    API view to list active branches.
    Accessible by any user.
    """
    permission_classes = [AllowAny]
    queryset = Branch.objects.filter(is_active=True)
    serializer_class = BranchSerializer


class BranchCreateListView(generics.ListCreateAPIView):
    """
    API view to list all branches or create a new branch.
    Accessible only by admin users for creation.
    """
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAdminUser]


class BranchDetailView(generics.RetrieveAPIView):
    """
    API view to retrieve details of a single active branch.
    Accessible by any user.
    """
    queryset = Branch.objects.filter(is_active=True)
    serializer_class = BranchSerializer


class BranchUpdateView(generics.RetrieveUpdateDestroyAPIView):
    """
    API view to retrieve, update, or delete a branch.
    Accessible only by admin users.
    """
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAdminUser]


class CheckoutView(APIView):
    """
    Handles the checkout process, including order creation, payment initiation (M-Pesa STK Push),
    and delivery creation.
    Requires authentication.
    """
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        """
        Processes the checkout request.
        """
        try:
            user = request.user
            logger.info(f"Received checkout request data: {request.data}")

            # Step 1: Validate input data
            serializer = CheckoutSerializer(data=request.data)
            if not serializer.is_valid():
                logger.error(f"Checkout validation failed: {serializer.errors}")
                return Response(
                    {"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST
                )

            validated_data = serializer.validated_data
            cart_items = validated_data["cart_items"]
            phone_number = validated_data["phone_number"]
            latitude = validated_data["latitude"]
            longitude = validated_data["longitude"]

            # Step 2: Calculate total amount
            total_amount = sum(
                float(item["product"]["price"]) * int(item["quantity"])
                for item in cart_items
            )

            # Step 3: Create the order
            order = Order.objects.create(
                customer=user,
                total_amount=total_amount,
                status="pending",
                payment_status="pending",
                payment_phone_number=phone_number,
                branch_id=validated_data["branch_id"],
            )
            logger.info(f"Order created: ID {order.id} for user {user.username}")

            # Step 4: Add order items
            for item in cart_items:
                OrderItem.objects.create(
                    order=order,
                    product_id=item["product"]["id"],
                    quantity=item["quantity"],
                    price=item["product"]["price"],
                )

            # Step 5: Initiate M-Pesa payment
            payment = Payment.objects.create(
                order=order,
                amount=total_amount,
                phone_number=phone_number,
                status="pending",
            )
            logger.info(f"Payment record created: ID {payment.id} for Order {order.id}")

            mpesa_service = MpesaService()
            callback_url = getattr(settings, "MPESA_CALLBACK_URL", None)
            if not callback_url:
                logger.error("MPESA_CALLBACK_URL not configured in settings")
                payment.status = "failed"
                payment.error_message = "Payment service configuration error: Callback URL missing"
                payment.save()
                return Response(
                    {"error": "Payment service configuration error"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            try:
                response = mpesa_service.stk_push(
                    phone_number=payment.phone_number,
                    amount=payment.amount,
                    account_reference=f"Order-{order.id}",
                    transaction_desc=f"Payment for Order {order.id}",
                    callback_url=callback_url,
                )

                if response.get("ResponseCode") == "0":
                    payment.checkout_request_id = response.get("CheckoutRequestID")
                    payment.save()
                    logger.info(
                        f"M-Pesa payment initiated, CheckoutRequestID: {payment.checkout_request_id}"
                    )
                else:
                    error_desc = response.get("ResponseDescription", "Unknown error")
                    logger.error(f"M-Pesa responded with error: {error_desc}")
                    payment.status = "failed"
                    payment.error_message = error_desc
                    payment.save()
                    order.status = "cancelled"
                    order.payment_status = "failed"
                    order.save()
                    return Response(
                        {
                            "error": f"Failed to initiate M-Pesa payment: {error_desc}",
                            "details": response,
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            except Exception as mpesa_error:
                error_message = str(mpesa_error)
                logger.error(f"M-Pesa request failed: {error_message}")
                payment.status = "failed"
                payment.error_message = f"M-Pesa request error: {error_message}"
                payment.save()
                order.status = "cancelled"
                order.payment_status = "failed"
                order.save()
                return Response(
                    {
                        "error": "Failed to connect to M-Pesa service",
                        "details": error_message,
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

            # Step 6: Create the delivery
            delivery_data = {
                "order_id": order.id,
                "latitude": latitude,
                "longitude": longitude,
            }
            delivery_serializer = DeliverySerializer(data=delivery_data)
            if not delivery_serializer.is_valid():
                logger.error(
                    f"Delivery validation failed: {delivery_serializer.errors}"
                )
                return Response(
                    {"error": delivery_serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            delivery = delivery_serializer.save()
            logger.info(f"Delivery created: ID {delivery.id} for Order {order.id}")

            # Step 7: Serialize the response
            order_serializer = OrderSerializer(order)
            return Response(
                {
                    "order": order_serializer.data,
                    "delivery_id": delivery.id,
                    "payment_status": payment.status,
                    "message": "Checkout initiated. Please complete the payment on your phone.",
                },
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            logger.error(
                f"Checkout failed for user {request.user.username}: {str(e)}"
            )
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentCallbackView(GenericAPIView):
    """
    Handles M-Pesa STK Push callbacks.
    Updates payment and order statuses based on the callback result.
    """

    def post(self, request, *args, **kwargs):
        """
        Processes the M-Pesa callback data.
        """
        try:
            logger.debug(f"Received M-Pesa callback: {request.data}")

            body = request.data.get("Body", {})
            stk_callback = body.get("stkCallback", {})
            checkout_request_id = stk_callback.get("CheckoutRequestID")
            result_code = stk_callback.get("ResultCode")
            result_desc = stk_callback.get("ResultDesc")

            logger.info(
                f"Processing callback with CheckoutRequestID: {checkout_request_id}, Result: {result_code}"
            )

            try:
                payment = Payment.objects.get(checkout_request_id=checkout_request_id)
                logger.info(f"Found payment: {payment.id} for order: {payment.order.id}")
            except Payment.DoesNotExist:
                logger.error(
                    f"Payment not found for CheckoutRequestID: {checkout_request_id}"
                )
                return Response(
                    {"detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND
                )

            if result_code == 0:
                payment.status = "successful"
                callback_metadata = stk_callback.get("CallbackMetadata", {}).get(
                    "Item", []
                )

                # Log all metadata for debugging
                logger.debug(f"Callback metadata: {callback_metadata}")

                for item in callback_metadata:
                    if item.get("Name") == "MpesaReceiptNumber":
                        payment.transaction_id = item.get("Value")
                        logger.info(f"Found transaction ID: {payment.transaction_id}")
                        break
            else:
                payment.status = "failed" if result_code == 1032 else "cancelled"
                payment.error_message = result_desc
                logger.warning(f"Payment failed/cancelled: {result_desc}")

            payment.save()
            payment.sync_order_status()  # Sync with Order
            logger.info(f"Updated payment status to: {payment.status}")
            return Response(
                {"ResultDesc": "Callback received successfully"}, status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Failed to process callback: {str(e)}")
            logger.error(traceback.format_exc())
            return Response(
                {"detail": f"Failed to process callback: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for API results.
    Sets default page size to 10, allows client to specify page_size, and limits max page size to 100.
    """
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class OrderListView(GenericAPIView, ListModelMixin, CreateModelMixin):
    """
    API view for listing and creating orders.
    Supports pagination and different permissions for GET and POST requests.
    """
    serializer_class = OrderSerializer
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        """
        Sets permissions based on the HTTP method.
        POST requests require authentication, GET requests require authentication and admin status.
        """
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsAdminUser()]

    def get_queryset(self):
        """
        Returns the queryset for orders based on user role.
        Admins can see all orders, regular users can only see their own orders.
        """
        user = self.request.user
        if user.is_admin:
            return Order.objects.all()
        return Order.objects.filter(customer=user)

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to list orders.
        """
        try:
            return self.list(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {"detail": f"Failed to fetch orders: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request, *args, **kwargs):
        """
        Handles POST requests to create a new order.
        """
        try:
            serializer = self.get_serializer(data=request.data, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(
                {"detail": "Invalid order data", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to create order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class OrderDetailView(RetrieveUpdateAPIView):
    """
    API view for retrieving and updating a single order.
    Supports partial updates and restricts updates for non-admin users.
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "id"

    def get_queryset(self):
        """
        Returns the queryset for orders based on user role.
        Admins can see all orders, regular users can only see their own orders.
        """
        user = self.request.user
        if user.is_admin:
            return Order.objects.all()
        return Order.objects.filter(customer=user)

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests to retrieve a specific order.
        """
        try:
            return self.retrieve(request, *args, **kwargs)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to fetch order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def patch(self, request, *args, **kwargs):
        """
        Handles PATCH requests for partial updates of an order.
        Non-admin users are restricted to updating only 'status' and 'payment_status'.
        """
        try:
            # Restrict updates to status and payment_status for non-admins
            if not request.user.is_admin:
                allowed_fields = {"status", "payment_status"}
                if set(request.data.keys()) - allowed_fields:
                    return Response(
                        {"detail": "Only status and payment_status can be updated"},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            return self.partial_update(request, *args, **kwargs)
        except Order.DoesNotExist:
            return Response(
                {"detail": "Order not found"}, status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {"detail": f"Failed to update order: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class AdminOrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for admin order management.
    Supports listing, retrieving, updating, and deleting orders.
    Includes filtering, searching, and ordering capabilities.
    """
    queryset = Order.objects.all().select_related("customer").prefetch_related("items__product")
    serializer_class = OrderSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "payment_status"]
    search_fields = ["customer__username", "id", "request_id"]
    ordering_fields = ["created_at", "total_amount", "id"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Optimizes query and applies search filtering.
        """
        queryset = super().get_queryset()
        search_query = self.request.query_params.get("search", None)
        if search_query:
            queryset = queryset.filter(
                Q(customer__username__icontains=search_query)
                | Q(id__icontains=search_query)
                | Q(request_id__icontains=search_query)
            )
        return queryset

    def create(self, request, *args, **kwargs):
        """
        Allows admins to create orders manually.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(customer=request.user)  # Set customer to admin or validate input
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):

        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Recalculate total if items are updated
        if "items" in request.data:
            instance.recalculate_total()

        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):

        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):

        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)