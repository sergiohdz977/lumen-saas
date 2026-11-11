from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User
from .models import Package, PhotographerProfile, PortfolioPhoto
from reviews.models import Review


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
            "user_id",
            "slug",
            "username",
            "studio_name",
            "profile_picture",
            "cover_image",
            "bio",
            "city",
            "specialties",
            "phone",
            "years_experience",
            "languages",
            "equipment",
            "is_published",
            "plan",
            "rating_avg",
            "rating_count",
            "created_at",
        }
        self.assertEqual(set(response.data.keys()), expected)

    def test_response_exposes_user_id(self):
        response = self.api.get("/api/profiles/ana-studio/")
        self.assertEqual(
            response.data["user_id"], self.photographer.pk
        )

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


class ProfileOwnershipAuditTests(TestCase):
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
        cls.maria = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
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
        cls.package = Package.objects.create(
            profile=cls.ana_profile, title="Boda completa", price=200
        )

    def test_portfolio_photo_create_ignores_profile_spoof(self):
        self.api = APIClient()
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/portfolio-photos/",
            {
                "profile": self.beto_profile.pk,
                "image": "https://example.com/port.jpg",
                "caption": "spoof",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        photo = PortfolioPhoto.objects.get(pk=response.data["id"])
        self.assertEqual(photo.profile, self.ana_profile)

    def test_customer_cannot_update_package(self):
        self.api = APIClient()
        self.api.force_authenticate(self.maria)
        response = self.api.patch(
            f"/api/packages/{self.package.pk}/",
            {"title": "hackeado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_delete_package(self):
        self.api = APIClient()
        self.api.force_authenticate(self.maria)
        response = self.api.delete(f"/api/packages/{self.package.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class ProfileUpdateEndpointsTests(TestCase):
    """Owner-only ``PATCH /api/profiles/{slug}/`` used by the web dashboard."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user(
            username="duena",
            email="duena@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.other = User.objects.create_user(
            username="otrafoto3",
            email="otrafoto3@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.customer = User.objects.create_user(
            username="cliente3",
            email="cliente3@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.profile = PhotographerProfile.objects.create(
            user=cls.owner,
            studio_name="Estudio Duena",
            slug="estudio-duena",
            city="Sevilla",
            is_published=True,
        )
        cls.hidden = PhotographerProfile.objects.create(
            user=cls.other,
            studio_name="Estudio Oculto",
            slug="estudio-oculto",
            is_published=False,
        )
        Package.objects.create(
            profile=cls.hidden, title="Sesion oculta", price="50.00"
        )

    def setUp(self):
        self.api = APIClient()

    def test_owner_can_update_own_profile(self):
        self.api.force_authenticate(self.owner)
        response = self.api.patch(
            "/api/profiles/estudio-duena/",
            {
                "studio_name": "Estudio Duena II",
                "bio": "Bodas y eventos",
                "city": "Malaga",
                "specialties": "weddings",
                "phone": "+34 600 000 000",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.studio_name, "Estudio Duena II")
        self.assertEqual(self.profile.city, "Malaga")
        self.assertEqual(self.profile.phone, "+34 600 000 000")

    def test_owner_can_publish_and_unpublish(self):
        self.api.force_authenticate(self.owner)
        response = self.api.patch(
            "/api/profiles/estudio-duena/", {"is_published": False}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.is_published)
        response = self.api.patch(
            "/api/profiles/estudio-duena/", {"is_published": True}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.is_published)

    def test_owner_can_update_own_unpublished_profile(self):
        self.api.force_authenticate(self.other)
        response = self.api.patch(
            "/api/profiles/estudio-oculto/", {"city": "Bogota"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hidden.refresh_from_db()
        self.assertEqual(self.hidden.city, "Bogota")

    def test_anonymous_update_denied(self):
        response = self.api.patch(
            "/api/profiles/estudio-duena/", {"studio_name": "Hack"}
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_customer_update_denied(self):
        self.api.force_authenticate(self.customer)
        response = self.api.patch(
            "/api/profiles/estudio-duena/", {"studio_name": "Hack"}
        )
        self.assertEqual(
            response.status_code, status.HTTP_403_FORBIDDEN
        )

    def test_other_photographer_cannot_update(self):
        self.api.force_authenticate(self.other)
        response = self.api.patch(
            "/api/profiles/estudio-duena/", {"studio_name": "Hack"}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_plan_cannot_be_changed(self):
        self.api.force_authenticate(self.owner)
        response = self.api.patch(
            "/api/profiles/estudio-duena/", {"plan": "pro"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, PhotographerProfile.PLAN_FREE)

    def test_delete_still_not_allowed(self):
        self.api.force_authenticate(self.owner)
        response = self.api.delete("/api/profiles/estudio-duena/")
        self.assertEqual(
            response.status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def test_photographer_lists_own_unpublished_catalog(self):
        self.api.force_authenticate(self.other)
        response = self.api.get("/api/packages/")
        titles = [p["title"] for p in response.data["results"]]
        self.assertIn("Sesion oculta", titles)

    def test_anonymous_list_still_hides_unpublished_catalog(self):
        response = self.api.get("/api/packages/")
        titles = [p["title"] for p in response.data["results"]]
        self.assertNotIn("Sesion oculta", titles)


class ProfileRatingPriceFilterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.rated = User.objects.create_user(
            username="starfotografa",
            email="star@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.low = User.objects.create_user(
            username="lowfotografa",
            email="low@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.rated_profile = PhotographerProfile.objects.create(
            user=cls.rated,
            studio_name="Star Studio",
            slug="star-studio",
            is_published=True,
        )
        cls.low_profile = PhotographerProfile.objects.create(
            user=cls.low,
            studio_name="Low Studio",
            slug="low-studio",
            is_published=True,
        )
        cls.unrated_profile = PhotographerProfile.objects.create(
            user=User.objects.create_user(
                username="sinresenas",
                email="sinresenas@test.com",
                password="secret123",
                role=User.ROLE_PHOTOGRAPHER,
            ),
            studio_name="Quiet Studio",
            slug="quiet-studio",
            is_published=True,
        )
        cls.customers = [
            User.objects.create_user(
                username=f"critico{n}",
                email=f"critico{n}@test.com",
                password="secret123",
                role=User.ROLE_CUSTOMER,
            )
            for n in range(3)
        ]
        Review.objects.create(
            photographer=cls.rated,
            customer=cls.customers[0],
            rating=5,
            comment="Amazing",
        )
        Review.objects.create(
            photographer=cls.rated,
            customer=cls.customers[1],
            rating=4,
        )
        Review.objects.create(
            photographer=cls.low,
            customer=cls.customers[0],
            rating=3,
        )
        cls.cheap = Package.objects.create(
            profile=cls.rated_profile,
            title="Basico",
            description="Una hora",
            price=100,
        )
        cls.premium = Package.objects.create(
            profile=cls.rated_profile,
            title="Premium",
            description="Todo el dia",
            price=500,
        )
        cls.pricey = Package.objects.create(
            profile=cls.low_profile,
            title="Caro",
            price=300,
        )

    def setUp(self):
        self.api = APIClient()

    def test_list_exposes_rating_average(self):
        response = self.api.get("/api/profiles/")
        ratings = {
            item["slug"]: item["rating_avg"]
            for item in response.data["results"]
        }
        self.assertEqual(ratings["star-studio"], 4.5)
        self.assertEqual(ratings["low-studio"], 3.0)
        self.assertIsNone(ratings["quiet-studio"])

    def test_list_exposes_rating_count(self):
        response = self.api.get("/api/profiles/")
        counts = {
            item["slug"]: item["rating_count"]
            for item in response.data["results"]
        }
        self.assertEqual(counts["star-studio"], 2)
        self.assertEqual(counts["low-studio"], 1)
        self.assertEqual(counts["quiet-studio"], 0)

    def test_profile_detail_exposes_rating_and_count(self):
        response = self.api.get("/api/profiles/star-studio/")
        self.assertEqual(response.data["rating_avg"], 4.5)
        self.assertEqual(response.data["rating_count"], 2)

    def test_profile_without_reviews_returns_null_rating(self):
        response = self.api.get("/api/profiles/quiet-studio/")
        self.assertIsNone(response.data["rating_avg"])
        self.assertEqual(response.data["rating_count"], 0)

    def test_filter_by_min_rating_keeps_only_high_rated(self):
        response = self.api.get("/api/profiles/?min_rating=4")
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["star-studio"])

    def test_min_rating_is_inclusive_at_the_boundary(self):
        response = self.api.get("/api/profiles/?min_rating=4.5")
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["star-studio"])

    def test_min_rating_rejects_non_numeric_value(self):
        response = self.api.get("/api/profiles/?min_rating=great")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_max_price_keeps_affordable_catalogs(self):
        response = self.api.get("/api/profiles/?max_price=150")
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["star-studio"])

    def test_max_price_rejects_non_numeric_value(self):
        response = self.api.get("/api/profiles/?max_price=cheap")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rating_and_price_filters_combine(self):
        response = self.api.get(
            "/api/profiles/?min_rating=4&max_price=150"
        )
        slugs = [item["slug"] for item in response.data["results"]]
        self.assertEqual(slugs, ["star-studio"])

    def test_rating_filter_combines_with_city(self):
        response = self.api.get(
            "/api/profiles/?min_rating=4&city=Nowhere"
        )
        self.assertEqual(response.data["count"], 0)


class ProfilePictureUploadTests(TestCase):
    PNG_BYTES = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
        b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    @classmethod
    def setUpTestData(cls):
        cls.photographer = User.objects.create_user(
            username="fotoperfil",
            email="fotoperfil@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.profile = PhotographerProfile.objects.create(
            user=cls.photographer,
            studio_name="Estudio Retrato",
            slug="estudio-retrato",
            is_published=True,
        )
        cls.customer = User.objects.create_user(
            username="clientefoto",
            email="clientefoto@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )

    def setUp(self):
        self.api = APIClient()

    def _upload(self, content=None, content_type="image/png", name="me.png"):
        file = SimpleUploadedFile(name, content or self.PNG_BYTES,
                                  content_type=content_type)
        return self.api.post(
            "/api/profiles/picture/",
            {"profile_picture": file},
            format="multipart",
        )

    def test_upload_requires_authentication(self):
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_rejects_customers(self):
        self.api.force_authenticate(self.customer)
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_upload_stores_image_and_returns_url(self):
        self.api.force_authenticate(self.photographer)
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        url = response.data["profile_picture"]
        self.assertTrue(url.startswith("/media/lumen/avatars/"))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.profile_picture, url)

    def test_upload_rejects_missing_file(self):
        self.api.force_authenticate(self.photographer)
        response = self.api.post("/api/profiles/picture/", {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_non_image_content_type(self):
        self.api.force_authenticate(self.photographer)
        response = self._upload(
            content=b"not-an-image", content_type="text/plain"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_rejects_files_over_two_megabytes(self):
        self.api.force_authenticate(self.photographer)
        oversized = b"0" * (2 * 1024 * 1024 + 1)
        response = self._upload(content=oversized, name="big.png")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_serializer_returns_null_without_picture(self):
        response = self.api.get("/api/profiles/estudio-retrato/")
        self.assertIsNone(response.data["profile_picture"])

    def test_serializer_returns_url_after_upload(self):
        self.api.force_authenticate(self.photographer)
        url = self._upload().data["profile_picture"]
        response = self.api.get("/api/profiles/estudio-retrato/")
        self.assertEqual(response.data["profile_picture"], url)

    def test_me_endpoint_exposes_picture(self):
        self.api.force_authenticate(self.photographer)
        url = self._upload().data["profile_picture"]
        response = self.api.get("/api/auth/me/")
        self.assertEqual(response.data["profile"]["profile_picture"], url)

    def test_profile_patch_cannot_inject_picture_url(self):
        self.api.force_authenticate(self.photographer)
        response = self.api.patch(
            "/api/profiles/estudio-retrato/",
            {"profile_picture": "https://evil.example/x.png"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.profile_picture, "")

    def test_delete_requires_authentication(self):
        response = self.api.delete("/api/profiles/picture/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_rejects_customers(self):
        self.api.force_authenticate(self.customer)
        response = self.api.delete("/api/profiles/picture/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_clears_picture_and_discards_file(self):
        self.api.force_authenticate(self.photographer)
        url = self._upload().data["profile_picture"]
        response = self.api.delete("/api/profiles/picture/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["profile_picture"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.profile_picture, "")
        detail = self.api.get("/api/profiles/estudio-retrato/")
        self.assertIsNone(detail.data["profile_picture"])
        me = self.api.get("/api/auth/me/")
        self.assertIsNone(me.data["profile"]["profile_picture"])

    def test_delete_without_picture_stays_idempotent(self):
        self.api.force_authenticate(self.photographer)
        response = self.api.delete("/api/profiles/picture/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["profile_picture"])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.profile_picture, "")
