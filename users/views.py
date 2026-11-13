from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.core.validators import EmailValidator
from django.contrib.auth.password_validation import validate_password
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
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


class AccountRecoveryView(APIView):
    """Start account recovery without revealing whether an email exists."""

    permission_classes = [AllowAny]

    def post(self, request):
        email = str(request.data.get("email") or "").strip().lower()
        action = request.data.get("action", "password")
        try:
            EmailValidator()(email)
        except DjangoValidationError:
            raise ValidationError({"email": "Enter a valid email address"})

        user = User.objects.filter(email__iexact=email).first()
        if user:
            if action == "username":
                subject = "Your Lumen username"
                message = (
                    f"Hi {user.username},\n\n"
                    f"Your Lumen username is: {user.username}\n\n"
                    "If you did not request this, you can ignore this email."
                )
            else:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                reset_url = (
                    f"{request.build_absolute_uri('/')}"
                    f"?reset={uid}:{token}"
                )
                subject = "Reset your Lumen password"
                message = (
                    f"Hi {user.username},\n\n"
                    "Use this link to choose a new Lumen password:\n\n"
                    f"{reset_url}\n\n"
                    "This link expires after it is used. If you did not request "
                    "this, you can ignore this email."
                )
            send_mail(subject, message, None, [user.email], fail_silently=True)

        return Response(
            {
                "detail": (
                    "If an account matches that email, instructions have been sent."
                )
            }
        )


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        uid = str(request.data.get("uid") or "")
        token = str(request.data.get("token") or "")
        new_password = str(request.data.get("new_password") or "")
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise ValidationError({"token": "This reset link is invalid or expired"})
        if not default_token_generator.check_token(user, token):
            raise ValidationError({"token": "This reset link is invalid or expired"})
        try:
            validate_password(new_password, user)
        except DjangoValidationError as error:
            raise ValidationError({"new_password": list(error.messages)})
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password updated. You can now log in."})
