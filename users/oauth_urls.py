# users/oauth_urls.py
from django.urls import path
from .views import GoogleLoginView, StoreStateView

urlpatterns = [
    path('auth/google/callback/', GoogleLoginView.as_view(), name='google_callback'),
    path('store-state/', StoreStateView.as_view(), name='store_state'),
]