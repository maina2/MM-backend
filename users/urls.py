from django.urls import path
from .views import RegisterView, LoginView, GoogleLoginView,UserProfileView,UserProfileUpdateView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'), 
    path('login/', LoginView.as_view(), name='login'),  
    path('google/', GoogleLoginView.as_view(), name='google_login'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile-update'),

]