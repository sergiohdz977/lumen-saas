from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import User
from .permissions import IsPhotographer


class PhotographerOnlyView(APIView):
    permission_classes = [IsPhotographer]

    def get(self, request):
        return Response({"ok": True})


class IsPhotographerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.photographer = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.customer = User.objects.create_user(
            username="luis",
            email="luis@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.factory = APIRequestFactory()

    def _request_with_user(self, user):
        request = self.factory.get("/")
        request.user = user
        return request
    
    def test_anonymous_user_is_denied(self):
        request = self._request_with_user(AnonymousUser())
        self.assertFalse(IsPhotographer().has_permission(request, None))

    def test_customer_is_denied(self):
        request = self._request_with_user(self.customer)
        self.assertFalse(IsPhotographer().has_permission(request, None))

    def test_photographer_is_allowed(self):
        request = self._request_with_user(self.photographer)
        self.assertTrue(IsPhotographer().has_permission(request, None))

    def test_message_is_in_spanish(self):
        self.assertEqual(
            IsPhotographer.message,
            "Solo los fotógrafos pueden realizar esta acción",
        )

    def test_view_rejects_customer(self):
        request = self.factory.get("/")
        force_authenticate(request, user=self.customer)
        response = PhotographerOnlyView.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.data["detail"],
            "Solo los fotógrafos pueden realizar esta acción",
        )

    def test_view_allows_photographer(self):
        request = self.factory.get("/")
        force_authenticate(request, user=self.photographer)
        response = PhotographerOnlyView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"ok": True})
