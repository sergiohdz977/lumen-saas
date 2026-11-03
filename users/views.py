from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import RegisterSerializer


class RegisterView(CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, "profile", None)
        data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        }
        if profile is not None:
            data["profile"] = {
                "studio_name": profile.studio_name,
                "slug": profile.slug,
                "bio": profile.bio,
                "city": profile.city,
                "specialties": profile.specialties,
                "phone": profile.phone,
                "plan": profile.plan,
                "is_published": profile.is_published,
                "profile_picture": profile.profile_picture or None,
                "stripe_connected": bool(profile.stripe_account_id),
            }
        return Response(data)

    def patch(self, request):
        """Update the caller's email and/or username (never the role)."""
        user = request.user
        changed = False
        if "email" in request.data:
            email = str(request.data["email"]).strip().lower()
            try:
                EmailValidator()(email)
            except DjangoValidationError:
                raise ValidationError(
                    {"email": "Enter a valid email address"}
                )
            if User.objects.filter(email__iexact=email).exclude(
                pk=user.pk
            ).exists():
                raise ValidationError(
                    {"email": "This email is already in use"}
                )
            user.email = email
            changed = True
        if "username" in request.data:
            username = str(request.data["username"]).strip()
            if not 3 <= len(username) <= 30:
                raise ValidationError(
                    {"username": "Username must be 3-30 characters"}
                )
            try:
                UnicodeUsernameValidator()(username)
            except DjangoValidationError:
                raise ValidationError(
                    {
                        "username": "Only letters, digits and @.+-_ are allowed"
                    }
                )
            if User.objects.filter(username__iexact=username).exclude(
                pk=user.pk
            ).exists():
                raise ValidationError(
                    {"username": "This username is already taken"}
                )
            user.username = username
            changed = True
        if changed:
            user.save()
        return Response(
            {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            }
        )


class ChangePasswordView(APIView):
    """``POST /api/auth/change-password/`` - JWT, current password required."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        current = request.data.get("current_password") or ""
        new = request.data.get("new_password") or ""
        if not request.user.check_password(current):
            raise ValidationError({"current_password": "Wrong password"})
        if len(new) < 8:
            raise ValidationError(
                {"new_password": "Password must be at least 8 characters"}
            )
        request.user.set_password(new)
        request.user.save(update_fields=["password"])
        return Response({"detail": "Password updated"})
