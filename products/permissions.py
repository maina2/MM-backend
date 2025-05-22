from rest_framework import permissions

class IsAdminUser(permissions.BasePermission):
    def has_permission(self, request, view):
        # Allow GET, HEAD, OPTIONS for all users
        if request.method in permissions.SAFE_METHODS:
            return True
        # Restrict POST, PUT, DELETE to users with role='admin'
        return request.user.is_authenticated and request.user.role == 'admin'

class IsDeliveryPerson(permissions.BasePermission):
    def has_permission(self, request, view):
        # Restrict all methods to users with role='delivery'
        return request.user.is_authenticated and request.user.role == 'delivery'