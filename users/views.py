from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser
from .serializers import CustomUserSerializer
from social_django.utils import load_strategy
from social_django.models import UserSocialAuth
from rest_framework.permissions import AllowAny
import logging


logger = logging.getLogger('social_django')

class RegisterView(APIView):
    def post(self, request):
        try:
            serializer = CustomUserSerializer(data=request.data)
            if serializer.is_valid():
                user = serializer.save()
                user.set_password(request.data['password'])
                user.save()
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                return Response(
                    {
                        "user": serializer.data,
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                    status=status.HTTP_201_CREATED
                )
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Failed to register user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LoginView(APIView):
    def post(self, request):
        try:
            username = request.data.get('username')
            password = request.data.get('password')
            user = authenticate(username=username, password=password)
            if user:
                # Generate JWT tokens
                refresh = RefreshToken.for_user(user)
                serializer = CustomUserSerializer(user)
                return Response(
                    {
                        "user": serializer.data,
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                    status=status.HTTP_200_OK
                )
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {"error": f"Failed to login: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # Step 1: Verify the Code is Received
        logger.debug(f"Request data: {request.data}")
        code = request.data.get('code')
        logger.debug(f"Received code: {code}")

        if not code or not isinstance(code, str):
            logger.error("Invalid or missing authorization code")
            return Response(
                {'error': 'Authorization code is missing or invalid'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Verify content type
        content_type = request.headers.get('Content-Type', '')
        if 'application/json' not in content_type.lower():
            logger.warning(f"Unexpected content type: {content_type}")
            return Response(
                {'error': 'Content-Type must be application/json'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Step 2: Debug the Code Exchange
            logger.debug("Loading social auth strategy...")
            strategy = load_strategy(request)
            backend = strategy.get_backend('google-oauth2')
            logger.debug(f"Backend loaded: {backend.name}")
            logger.debug(f"Backend config - Client ID: {backend.setting('KEY')}")

            # Redirect URI is set in settings.py, no need to override here
            redirect_uri = backend.setting('REDIRECT_URI', 'http://localhost:5173/auth/google/callback')
            logger.debug(f"Using redirect URI: {redirect_uri}")

            logger.info("Attempting code exchange with Google...")
            user = backend.complete(request=request, code=code)
            logger.debug(f"User after code exchange: {user}")

            if not user:
                logger.error("No user returned from backend.complete")
                return Response(
                    {'error': 'Authentication failed: No user found'},
                    status=status.HTTP_401_UNAUTHORIZED
                )

            # Check or create social auth record
            try:
                social_user = UserSocialAuth.objects.get(user=user)
            except UserSocialAuth.DoesNotExist:
                logger.warning(f"No social auth record for user: {user}")
                return Response(
                    {'error': 'Social auth record not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Serialize user data
            serializer = CustomUserSerializer(user)
            user_data = serializer.data

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': user_data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Code exchange failed: {type(e).__name__}: {str(e)}", exc_info=True)
            return Response(
                {'error': f"Authentication error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )