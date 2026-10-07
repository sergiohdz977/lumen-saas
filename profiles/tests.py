from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from .models import PhotographerProfile


class PublicProfileEndpointsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.photographer = User.objects.create_user(
            username="fotografa",
            email="fotografa@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.other_photographer = User.objects.create_user(
            username="otrofoto",
            email="otro@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.published = PhotographerProfile.objects.create(
            user=cls.photographer,
            studio_name="Ana Studio",
            slug="ana-studio",
            bio="Fotografia de bodas",
            city="La Habana",
            specialties="weddings, portraits",
            is_published=True,
        )
        cls.unpublished = PhotographerProfile.objects.create(
            user=cls.other_photographer,
            studio_name="Estudio Secreto",
            slug="estudio-secreto",
            is_published=False,
        )

    def setUp(self):
        self.api = APIClient()

    def test_list_does_not_require_authentication(self):
        response = self.api.get("/api/profiles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_shows_published_profiles(self):
        response = self.api.get("/api/profiles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["slug"], "ana-studio")

    def test_detail_published_profile_by_slug(self):
        response = self.api.get("/api/profiles/ana-studio/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["studio_name"], "Ana Studio")
        self.assertEqual(response.data["username"], "fotografa")
        self.assertEqual(response.data["city"], "La Habana")

    def test_detail_unpublished_profile_returns_404(self):
        response = self.api.get("/api/profiles/estudio-secreto/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_is_read_only(self):
        response = self.api.post(
            "/api/profiles/",
            {"studio_name": "Hack"},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_detail_is_read_only(self):
        response = self.api.put(
            "/api/profiles/ana-studio/",
            {"studio_name": "Hack"},
            format="json",
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_response_exposes_expected_fields(self):
        response = self.api.get("/api/profiles/ana-studio/")
        expected = {
            "id",
            "slug",
            "username",
            "studio_name",
            "bio",
            "city",
            "specialties",
            "phone",
            "created_at",
        }
        self.assertEqual(set(response.data.keys()), expected)

    def test_slug_is_generated_automatically(self):
        user = User.objects.create_user(
            username="luz",
            email="luz@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        profile = PhotographerProfile.objects.create(
            user=user,
            studio_name="Luz Caribe",
            is_published=True,
        )
        self.assertEqual(profile.slug, "luz-caribe")

    def test_slug_is_unique(self):
        from django.db import IntegrityError
        user_a = User.objects.create_user(
            username="dup_a",
            email="dupa@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        user_b = User.objects.create_user(
            username="dup_b",
            email="dupb@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        PhotographerProfile.objects.create(
            user=user_a,
            studio_name="Dup",
            slug="mismo-slug",
        )
        with self.assertRaises(IntegrityError):
            PhotographerProfile.objects.create(
                user=user_b,
                studio_name="Dup 2",
                slug="mismo-slug",
            )
