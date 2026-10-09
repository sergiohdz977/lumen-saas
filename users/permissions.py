from rest_framework.permissions import BasePermission
from .models import User


class IsPhotographer(BasePermission):
    message = "Solo los fotógrafos pueden realizar esta acción"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.ROLE_PHOTOGRAPHER
        )


class IsCustomer(BasePermission):
    message = "Solo los clientes pueden realizar esta acción"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.ROLE_CUSTOMER
        )
