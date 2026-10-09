from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from .models import Package, PhotographerProfile, PortfolioPhoto


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
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "ana-studio")

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

    def test_filter_by_city_returns_matching_profiles(self):
        user = User.objects.create_user(
            username="santiago",
            email="santiago@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        PhotographerProfile.objects.create(
            user=user,
            studio_name="Estudio Sur",
            slug="estudio-sur",
            city="Santiago de Cuba",
            specialties="portraits",
            is_published=True,
        )
        response = self.api.get("/api/profiles/?city=santiago")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "estudio-sur")

    def test_filter_by_city_is_case_insensitive(self):
        response = self.api.get("/api/profiles/?city=LA+HABANA")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "ana-studio")

    def test_filter_by_specialty_returns_matching_profiles(self):
        user = User.objects.create_user(
            username="retratos",
            email="retratos@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        PhotographerProfile.objects.create(
            user=user,
            studio_name="Solo Retratos",
            slug="solo-retratos",
            city="Matanzas",
            specialties="portraits",
            is_published=True,
        )
        response = self.api.get("/api/profiles/?specialty=wedding")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = [p["slug"] for p in response.data["results"]]
        self.assertIn("ana-studio", slugs)
        self.assertNotIn("solo-retratos", slugs)

    def test_filter_with_no_match_returns_empty(self):
        response = self.api.get("/api/profiles/?city=ciudad-inexistente")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])

    def test_filters_can_be_combined(self):
        response = self.api.get("/api/profiles/?city=habana&specialty=portraits")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "ana-studio")

    def _create_published_profiles(self, quantity):
        for i in range(quantity):
            user = User.objects.create_user(
                username=f"pag{i}",
                email=f"pag{i}@test.com",
                password="secret123",
                role=User.ROLE_PHOTOGRAPHER,
            )
            PhotographerProfile.objects.create(
                user=user,
                studio_name=f"Studio {i}",
                slug=f"studio-{i}",
                is_published=True,
            )

    def test_list_is_paginated(self):
        self._create_published_profiles(12)
        response = self.api.get("/api/profiles/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 13)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNone(response.data["previous"])

    def test_second_page_returns_the_rest(self):
        self._create_published_profiles(12)
        response = self.api.get("/api/profiles/?page=2")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 3)
        self.assertIsNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_filter_and_pagination_work_together(self):
        self._create_published_profiles(12)
        response = self.api.get("/api/profiles/?city=inexistente&page=2")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

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


class PackageEndpointsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.beto = User.objects.create_user(
            username="beto",
            email="beto@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.caro = User.objects.create_user(
            username="caro",
            email="caro@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.customer = User.objects.create_user(
            username="cliente",
            email="cliente@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.no_profile_user = User.objects.create_user(
            username="sinperfil",
            email="sinperfil@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.ana_profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.beto_profile = PhotographerProfile.objects.create(
            user=cls.beto,
            studio_name="Beto Studio",
            slug="beto-studio",
            is_published=True,
        )
        cls.caro_profile = PhotographerProfile.objects.create(
            user=cls.caro,
            studio_name="Caro Studio",
            slug="caro-studio",
            is_published=False,
        )
        cls.package_ana = Package.objects.create(
            profile=cls.ana_profile,
            title="Boda completa",
            description="Ceremonia y fiesta",
            price=200,
        )
        cls.package_beto = Package.objects.create(
            profile=cls.beto_profile,
            title="Retrato",
            price=50,
        )
        cls.package_caro = Package.objects.create(
            profile=cls.caro_profile,
            title="Oculta",
            price=10,
        )

    def setUp(self):
        self.api = APIClient()

    def test_list_is_public(self):
        response = self.api.get("/api/packages/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_list_only_shows_published_profiles_packages(self):
        response = self.api.get("/api/packages/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [p["title"] for p in response.data["results"]]
        self.assertEqual(response.data["count"], 2)
        self.assertIn("Boda completa", titles)
        self.assertIn("Retrato", titles)
        self.assertNotIn("Oculta", titles)

    def test_list_filter_by_profile_slug(self):
        response = self.api.get("/api/packages/?profile=ana-studio")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Boda completa")

    def test_detail_published_package(self):
        response = self.api.get(f"/api/packages/{self.package_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["price"], "200.00")
        self.assertEqual(response.data["profile_slug"], "ana-studio")
        self.assertEqual(response.data["studio_name"], "Ana Studio")

    def test_detail_unpublished_profile_package_returns_404(self):
        response = self.api.get(f"/api/packages/{self.package_caro.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_create_is_denied(self):
        response = self.api.post(
            "/api/packages/",
            {"title": "Hack", "price": "10.00"},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_customer_create_is_denied(self):
        self.api.force_authenticate(self.customer)
        response = self.api.post(
            "/api/packages/",
            {"title": "Hack", "price": "10.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_creates_package_on_own_profile(self):
        self.api.force_authenticate(self.ana)
        payload = {"title": "Sesion parejas", "price": "80.00"}
        response = self.api.post("/api/packages/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        package = Package.objects.get(title="Sesion parejas")
        self.assertEqual(package.profile, self.ana_profile)
        self.assertEqual(response.data["profile_slug"], "ana-studio")

    def test_photographer_without_profile_cannot_create(self):
        self.api.force_authenticate(self.no_profile_user)
        payload = {"title": "Sin perfil", "price": "10.00"}
        response = self.api.post("/api/packages/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_package_create_ignores_profile_sent_by_client(self):
        self.api.force_authenticate(self.ana)
        payload = {
            "title": "Intento Spoof",
            "price": "10.00",
            "profile": self.beto_profile.pk,
        }
        response = self.api.post("/api/packages/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        package = Package.objects.get(title="Intento Spoof")
        self.assertEqual(package.profile, self.ana_profile)

    def test_update_own_package(self):
        self.api.force_authenticate(self.ana)
        response = self.api.patch(
            f"/api/packages/{self.package_ana.pk}/",
            {"price": "250.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.package_ana.refresh_from_db()
        self.assertEqual(str(self.package_ana.price), "250.00")

    def test_cannot_update_others_package(self):
        self.api.force_authenticate(self.ana)
        response = self.api.patch(
            f"/api/packages/{self.package_beto.pk}/",
            {"price": "1.00"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_own_package(self):
        self.api.force_authenticate(self.ana)
        response = self.api.delete(f"/api/packages/{self.package_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Package.objects.filter(pk=self.package_ana.pk).exists())

    def test_cannot_delete_others_package(self):
        self.api.force_authenticate(self.ana)
        response = self.api.delete(f"/api/packages/{self.package_beto.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Package.objects.filter(pk=self.package_beto.pk).exists())

    def test_negative_price_rejected(self):
        self.api.force_authenticate(self.ana)
        payload = {"title": "Negativo", "price": "-5.00"}
        response = self.api.post("/api/packages/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PortfolioPhotoEndpointsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.caro = User.objects.create_user(
            username="caro",
            email="caro@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.customer = User.objects.create_user(
            username="cliente",
            email="cliente@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.ana_profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
            is_published=True,
        )
        cls.caro_profile = PhotographerProfile.objects.create(
            user=cls.caro,
            studio_name="Caro Studio",
            slug="caro-studio",
            is_published=False,
        )
        cls.photo_ana = PortfolioPhoto.objects.create(
            profile=cls.ana_profile,
            image="https://cdn.example.com/foto1.jpg",
            caption="Playa",
        )
        cls.photo_caro = PortfolioPhoto.objects.create(
            profile=cls.caro_profile,
            image="https://cdn.example.com/foto2.jpg",
            caption="Oculta",
        )

    def setUp(self):
        self.api = APIClient()

    def test_list_only_shows_published_profiles_photos(self):
        response = self.api.get("/api/portfolio-photos/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["caption"], "Playa")

    def test_detail_published_photo(self):
        response = self.api.get(f"/api/portfolio-photos/{self.photo_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile_slug"], "ana-studio")

    def test_detail_unpublished_profile_photo_returns_404(self):
        response = self.api.get(f"/api/portfolio-photos/{self.photo_caro.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_create_is_denied(self):
        response = self.api.post(
            "/api/portfolio-photos/",
            {"image": "https://cdn.example.com/x.jpg"},
            format="json",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_customer_create_is_denied(self):
        self.api.force_authenticate(self.customer)
        response = self.api.post(
            "/api/portfolio-photos/",
            {"image": "https://cdn.example.com/x.jpg"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_creates_photo_on_own_profile(self):
        self.api.force_authenticate(self.ana)
        payload = {
            "image": "https://cdn.example.com/nueva.jpg",
            "caption": "Nuevo trabajo",
        }
        response = self.api.post("/api/portfolio-photos/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        photo = PortfolioPhoto.objects.get(caption="Nuevo trabajo")
        self.assertEqual(photo.profile, self.ana_profile)

    def test_cannot_update_others_photo(self):
        self.api.force_authenticate(self.ana)
        response = self.api.patch(
            f"/api/portfolio-photos/{self.photo_caro.pk}/",
            {"caption": "Hack"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_own_photo(self):
        self.api.force_authenticate(self.ana)
        response = self.api.delete(f"/api/portfolio-photos/{self.photo_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            PortfolioPhoto.objects.filter(pk=self.photo_ana.pk).exists()
        )
