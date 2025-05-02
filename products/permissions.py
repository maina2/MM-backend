from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS requests for all users (read-only)
        if request.method in permissions.SAFE_METHODS:
            return True
        # For other methods (POST, PUT, DELETE), require authenticated admin
        return request.user.is_authenticated and request.user.is_admin

class IsDeliveryPerson(permissions.BasePermission):
    def has_permission(self, request, view):
        # Require authenticated delivery person for all methods
        return request.user.is_authenticated and request.user.is_delivery_person