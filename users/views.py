# users/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.mixins import ListModelMixin, CreateModelMixin, UpdateModelMixin, DestroyModelMixin
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from .models import CustomUser
from .serializers import CustomUserSerializer, UserUpdateSerializer, AdminUserSerializer
from .permissions import IsAdminUser
from django.conf import settings
from rest_framework.permissions import IsAuthenticated, AllowAny
import requests
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
        code = request.data.get('code')
        logger.debug(f"Received code: {code}")

        if not code or not isinstance(code, str):
            logger.error("Invalid or missing authorization code")
            return Response(
                {'error': 'Authorization code is missing or invalid'},
                status=status.HTTP_400_BAD_REQUEST
            )

        token_url = 'https://oauth2.googleapis.com/token'
        token_data = {
            'code': code,
            'client_id': settings.GOOGLE_CLIENT_ID,
            'client_secret': settings.GOOGLE_CLIENT_SECRET,
            'redirect_uri': settings.GOOGLE_REDIRECT_URI,
            'grant_type': 'authorization_code',
        }

        try:
            token_response = requests.post(token_url, data=token_data)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get('access_token')
            logger.debug(f"Access token received: {access_token}")

            user_info_url = 'https://www.googleapis.com/oauth2/v3/userinfo'
            user_info_response = requests.get(
                user_info_url,
                headers={'Authorization': f'Bearer {access_token}'}
            )
            user_info_response.raise_for_status()
            user_info = user_info_response.json()
            logger.debug(f"User info: {user_info}")

            email = user_info.get('email')
            name = user_info.get('name', '')
            google_id = user_info.get('sub')

            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                user = CustomUser.objects.create(
                    email=email,
                    username=email.split('@')[0],
                    first_name=name.split()[0] if name else '',
                    last_name=' '.join(name.split()[1:]) if name else '',
                    is_active=True
                )
                user.set_unusable_password()
                user.save()

            refresh = RefreshToken.for_user(user)
            serializer = CustomUserSerializer(user)
            return Response({
                'user': serializer.data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)

        except requests.exceptions.RequestException as e:
            logger.error(f"Token exchange failed: {str(e)}")
            return Response(
                {'error': f"Authentication error: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            return Response(
                {'error': f"Unexpected error: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserProfileView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        serializer = CustomUserSerializer(request.user)
        return Response(serializer.data)

class UserProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated]
    def put(self, request):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AdminUserListCreateView(GenericAPIView, ListModelMixin, CreateModelMixin):
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, *args, **kwargs):
        try:
            logger.info(f"Admin {request.user.username} fetching user list")
            return self.list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Failed to fetch users: {str(e)}")
            return Response(
                {"error": f"Failed to fetch users: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def post(self, request, *args, **kwargs):
        try:
            logger.info(f"Admin {request.user.username} creating user")
            return self.create(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Failed to create user: {str(e)}")
            return Response(
                {"error": f"Failed to create user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class AdminUserUpdateDeleteView(GenericAPIView, UpdateModelMixin, DestroyModelMixin):
    queryset = CustomUser.objects.all()
    serializer_class = AdminUserSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]

    def put(self, request, *args, **kwargs):
        try:
            logger.info(f"Admin {request.user.username} updating user {kwargs.get('pk')}")
            return self.update(request, *args, **kwargs)
        except CustomUser.DoesNotExist:
            logger.error(f"User {kwargs.get('pk')} not found")
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to update user: {str(e)}")
            return Response(
                {"error": f"Failed to update user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def patch(self, request, *args, **kwargs):
        try:
            logger.info(f"Admin {request.user.username} partially updating user {kwargs.get('pk')}")
            return self.partial_update(request, *args, **kwargs)
        except CustomUser.DoesNotExist:
            logger.error(f"User {kwargs.get('pk')} not found")
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to update user: {str(e)}")
            return Response(
                {"error": f"Failed to update user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def delete(self, request, *args, **kwargs):
        try:
            logger.info(f"Admin {request.user.username} deleting user {kwargs.get('pk')}")
            return self.destroy(request, *args, **kwargs)
        except CustomUser.DoesNotExist:
            logger.error(f"User {kwargs.get('pk')} not found")
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Failed to delete user: {str(e)}")
            return Response(
                {"error": f"Failed to delete user: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )