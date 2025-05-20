# users/permissions.py
from rest_framework.permissions import BasePermission

class IsAdminUser(BasePermission):
    """Grants access to authenticated users with 'admin' role."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'admin'
        )

class IsDeliveryUser(BasePermission):
    """Grants access to authenticated users with 'delivery' role."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'delivery'
        )

class IsCustomerUser(BasePermission):
    """Grants access to authenticated users with 'customer' role."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            hasattr(request.user, 'role') and
            request.user.role == 'customer'
        )