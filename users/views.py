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
        code = request.data.get('code')
        print(f"Received code: {code}")
        if not code:
            return Response({'error': 'Authorization code not provided'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Load the social auth strategy
            strategy = load_strategy(request)
            backend = strategy.get_backend('google-oauth2')
            print(f"Backend loaded: {backend.name}")

            # Set the redirect URI explicitly
            redirect_uri = 'http://localhost:5173/auth/google/callback'
            backend.REDIRECT_URI = redirect_uri
            print(f"Set redirect URI: {redirect_uri}")

            # Exchange the code for an access token and user data
            user = backend.complete(request=request, code=code)
            print(f"User after code exchange: {user}")

            if not user:
                return Response({'error': 'Authentication failed'}, status=status.HTTP_401_UNAUTHORIZED)

            # Check if the user exists, or create a new one
            social_user = UserSocialAuth.objects.get(user=user)
            user_data = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone_number': getattr(user, 'phone_number', ''),
                'is_admin': user.is_admin,
                'is_delivery_person': getattr(user, 'is_delivery_person', False),
            }

            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': user_data,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            }, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error during code exchange: {str(e)}")
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)