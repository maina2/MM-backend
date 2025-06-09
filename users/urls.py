# users/urls.py
from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    GoogleLoginView,
    UserProfileView,
    UserProfileUpdateView,
    AdminUserListCreateView,
    AdminUserUpdateDeleteView,
    AdminStatsView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('google/',GoogleLoginView.as_view(), name='google_login'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('profile/update/', UserProfileUpdateView.as_view(), name='profile-update'),
    path('manage/users/', AdminUserListCreateView.as_view(), name='manage-user-list'),
    path('manage/users/<int:pk>/', AdminUserUpdateDeleteView.as_view(), name='manage-user-detail'),
    path("manage/stats/", AdminStatsView.as_view(), name="admin-stats"),

]