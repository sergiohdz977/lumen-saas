from django.contrib.auth.models import AnonymousUser
from django.test import TestCase
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from rest_framework import status
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


class RegisterEndpointTests(TestCase):
    def setUp(self):
        self.api = APIClient()

    def test_register_photographer(self):
        payload = {
            "username": "nuevafoto",
            "email": "nuevafoto@test.com",
            "password": "secret123",
            "role": "photographer",
        }
        response = self.api.post("/api/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["role"], "photographer")
        user = User.objects.get(username="nuevafoto")
        self.assertEqual(user.role, User.ROLE_PHOTOGRAPHER)
        self.assertTrue(user.check_password("secret123"))

    def test_register_without_role_defaults_to_customer(self):
        payload = {
            "username": "nuevocliente",
            "email": "nuevocliente@test.com",
            "password": "secret123",
        }
        response = self.api.post("/api/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="nuevocliente")
        self.assertEqual(user.role, User.ROLE_CUSTOMER)

    def test_register_duplicate_email_rejected(self):
        User.objects.create_user(
            username="ocupado",
            email="ocupado@test.com",
            password="secret123",
        )
        payload = {
            "username": "otro",
            "email": "ocupado@test.com",
            "password": "secret123",
        }
        response = self.api.post("/api/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Este correo ya existe", str(response.data))

    def test_register_short_password_rejected(self):
        payload = {
            "username": "corto",
            "email": "corto@test.com",
            "password": "1234567",
        }
        response = self.api.post("/api/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_username_rejected(self):
        User.objects.create_user(
            username="existente",
            email="existente@test.com",
            password="secret123",
        )
        payload = {
            "username": "existente",
            "email": "libre@test.com",
            "password": "secret123",
        }
        response = self.api.post("/api/auth/register/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_does_not_expose_password(self):
        payload = {
            "username": "seguro",
            "email": "seguro@test.com",
            "password": "secret123",
        }
        response = self.api.post("/api/auth/register/", payload, format="json")
        self.assertNotIn("password", response.data)


class LoginAndRefreshTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="fotografa",
            email="fotografa@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )

    def setUp(self):
        self.api = APIClient()

    def test_login_returns_tokens(self):
        response = self.api.post(
            "/api/auth/login/",
            {"username": "fotografa", "password": "secret123"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_rejected(self):
        response = self.api.post(
            "/api/auth/login/",
            {"username": "fotografa", "password": "mala1234"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_with_valid_token(self):
        login = self.api.post(
            "/api/auth/login/",
            {"username": "fotografa", "password": "secret123"},
            format="json",
        )
        response = self.api.post(
            "/api/auth/token/refresh/",
            {"refresh": login.data["refresh"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_refresh_with_invalid_token_rejected(self):
        response = self.api.post(
            "/api/auth/token/refresh/",
            {"refresh": "token-falso-xyz"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_response_has_no_password(self):
        response = self.api.post(
            "/api/auth/login/",
            {"username": "fotografa", "password": "secret123"},
            format="json",
        )
        self.assertNotIn("password", response.data)
