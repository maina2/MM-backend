from django.urls import path
from .views import RegisterView, LoginView, GoogleLoginView,GoogleAuthInitiateView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'), 
    path('login/', LoginView.as_view(), name='login'),  
    path('google/', GoogleLoginView.as_view(), name='google_login'),
    path('google/initiate/', GoogleAuthInitiateView.as_view(), name='google_initiate'),

]