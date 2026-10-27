from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

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
                "stripe_connected": bool(profile.stripe_account_id),
            }
        return Response(data)
