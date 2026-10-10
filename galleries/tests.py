from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from clients.models import Client
from shoots.models import Shoot
from users.models import User
from .models import Gallery, Photo


class GalleryAccessTests(TestCase):
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
        cls.pedro = User.objects.create_user(
            username="pedro",
            email="pedro@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.luis = User.objects.create_user(
            username="luis",
            email="luis@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.client_maria = Client.objects.create(
            photographer=cls.ana, user=cls.maria, name="Maria F"
        )
        cls.client_pedro = Client.objects.create(
            photographer=cls.beto, user=cls.pedro, name="Pedro F"
        )
        cls.shoot_ana = Shoot.objects.create(
            client=cls.client_maria,
            title="Boda de Maria",
            shoot_type="boda",
            date="2026-11-20T10:00:00Z",
        )
        cls.shoot_beto = Shoot.objects.create(
            client=cls.client_pedro,
            title="Retrato de Pedro",
            shoot_type="retrato",
            date="2026-11-21T10:00:00Z",
        )
        cls.gallery_ana = Gallery.objects.create(shoot=cls.shoot_ana)
        cls.photo_ana = Photo.objects.create(
            gallery=cls.gallery_ana,
            image="https://example.com/foto1.jpg",
            caption="Primera",
        )

    def setUp(self):
        self.api = APIClient()

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/galleries/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_customer_create_is_denied(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/galleries/", {"shoot": self.shoot_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_creates_gallery_for_own_shoot(self):
        self.api.force_authenticate(self.beto)
        response = self.api.post(
            "/api/galleries/", {"shoot": self.shoot_beto.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["client_username"], "pedro")
        self.assertTrue(Gallery.objects.filter(shoot=self.shoot_beto).exists())

    def test_photographer_cannot_create_gallery_for_others_shoot(self):
        second_shoot_ana = Shoot.objects.create(
            client=self.client_maria,
            title="Preboda de Maria",
            shoot_type="preboda",
            date="2026-11-19T10:00:00Z",
        )
        self.api.force_authenticate(self.beto)
        response = self.api.post(
            "/api/galleries/", {"shoot": second_shoot_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("no es tuya", str(response.data))

    def test_shoot_can_have_only_one_gallery(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/galleries/", {"shoot": self.shoot_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ya tiene", str(response.data))

    def test_photographer_lists_only_own_galleries(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/galleries/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["id"], self.gallery_ana.pk)

    def test_customer_lists_only_own_galleries(self):
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/galleries/")
        self.assertEqual(response.data["count"], 1)
        self.api.force_authenticate(self.luis)
        response = self.api.get("/api/galleries/")
        self.assertEqual(response.data["count"], 0)

    def test_other_customer_cannot_retrieve_gallery(self):
        self.api.force_authenticate(self.luis)
        response = self.api.get(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_other_photographer_cannot_retrieve_gallery(self):
        self.api.force_authenticate(self.beto)
        response = self.api.get(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_customer_cannot_update_gallery(self):
        self.api.force_authenticate(self.maria)
        response = self.api.patch(
            f"/api/galleries/{self.gallery_ana.pk}/", {}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_delete_gallery(self):
        self.api.force_authenticate(self.maria)
        response = self.api.delete(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_deletes_own_gallery_with_photos(self):
        self.api.force_authenticate(self.ana)
        response = self.api.delete(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Gallery.objects.filter(pk=self.gallery_ana.pk).exists())
        self.assertFalse(Photo.objects.filter(pk=self.photo_ana.pk).exists())

    def test_list_filter_by_shoot(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get(f"/api/galleries/?shoot={self.shoot_ana.pk}")
        self.assertEqual(response.data["count"], 1)
        response = self.api.get(f"/api/galleries/?shoot={self.shoot_beto.pk}")
        self.assertEqual(response.data["count"], 0)


class PhotoAccessTests(TestCase):
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
        cls.luis = User.objects.create_user(
            username="luis",
            email="luis@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.client_maria = Client.objects.create(
            photographer=cls.ana, user=cls.maria, name="Maria F"
        )
        cls.shoot_ana = Shoot.objects.create(
            client=cls.client_maria,
            title="Boda de Maria",
            shoot_type="boda",
            date="2026-11-20T10:00:00Z",
        )
        cls.gallery_ana = Gallery.objects.create(shoot=cls.shoot_ana)
        cls.photo_ana = Photo.objects.create(
            gallery=cls.gallery_ana,
            image="https://example.com/foto1.jpg",
            caption="Primera",
        )

    def setUp(self):
        self.api = APIClient()

    def test_anonymous_list_is_denied(self):
        response = self.api.get("/api/photos/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_customer_create_is_denied(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/photos/",
            {"gallery": self.gallery_ana.pk, "image": "https://example.com/x.jpg"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_adds_photo_to_own_gallery(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/",
            {"gallery": self.gallery_ana.pk, "image": "https://example.com/n.jpg"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Photo.objects.count(), 2)

    def test_photographer_cannot_add_photo_to_others_gallery(self):
        beto_profile_shoot_client = Client.objects.create(
            photographer=self.beto, name="Manual"
        )
        beto_shoot = Shoot.objects.create(
            client=beto_profile_shoot_client,
            title="Sesion beto",
            shoot_type="retrato",
            date="2026-12-01T10:00:00Z",
        )
        beto_gallery = Gallery.objects.create(shoot=beto_shoot)
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/",
            {"gallery": beto_gallery.pk, "image": "https://example.com/hack.jpg"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Photo.objects.count(), 1)

    def test_customer_sees_only_own_photos(self):
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/photos/")
        self.assertEqual(response.data["count"], 1)
        self.api.force_authenticate(self.luis)
        response = self.api.get("/api/photos/")
        self.assertEqual(response.data["count"], 0)

    def test_customer_cannot_update_photo(self):
        self.api.force_authenticate(self.maria)
        response = self.api.patch(
            f"/api/photos/{self.photo_ana.pk}/",
            {"caption": "hackeada"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_updates_own_photo(self):
        self.api.force_authenticate(self.ana)
        response = self.api.patch(
            f"/api/photos/{self.photo_ana.pk}/",
            {"caption": "Editada"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.photo_ana.refresh_from_db()
        self.assertEqual(self.photo_ana.caption, "Editada")

    def test_list_filter_by_gallery(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get(f"/api/photos/?gallery={self.gallery_ana.pk}")
        self.assertEqual(response.data["count"], 1)
        response = self.api.get("/api/photos/?gallery=9999")
        self.assertEqual(response.data["count"], 0)
