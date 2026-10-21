from rest_framework.permissions import BasePermission
from .models import User


class IsPhotographer(BasePermission):
    message = "Only photographers can perform this action"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.ROLE_PHOTOGRAPHER
        )


class IsCustomer(BasePermission):
    message = "Only customers can perform this action"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == User.ROLE_CUSTOMER
        )
