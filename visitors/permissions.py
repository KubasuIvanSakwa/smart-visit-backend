from rest_framework import permissions


class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_superuser


class IsReceptionistUser(permissions.BasePermission):
    """
    Allows access to users who are marked as receptionists.
    You may customize this logic as per your User model.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and hasattr(request.user, 'userprofile') and request.user.userprofile.role == 'receptionist'
