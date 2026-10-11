from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework import status

from clients.models import Client
from shoots.models import Shoot
from users.models import User
from .models import Gallery, Photo


def fake_image(name="foto.jpg"):
    return SimpleUploadedFile(
        name, b"\xff\xd8\xff\xe0fakejpegbytes", content_type="image/jpeg"
    )


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
            {"gallery": self.gallery_ana.pk, "image": fake_image()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Photo.objects.count(), 2)
        photo = Photo.objects.get(caption="")
        self.assertTrue(photo.image)
        self.assertTrue(photo.image.startswith("/media/"))

    def test_image_is_required_on_create(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/",
            {"gallery": self.gallery_ana.pk},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("image", response.data)

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
            {"gallery": beto_gallery.pk, "image": fake_image("hack.jpg")},
            format="multipart",
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


class ShareLinkTests(TestCase):
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

    def _token_from(self, url):
        return url.rstrip("/").split("/")[-1]

    def _share(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/galleries/{self.gallery_ana.pk}/share-link/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data

    def test_photographer_gets_share_link(self):
        data = self._share()
        self.assertIn("/api/gallery-view/", data["url"])
        self.assertEqual(data["expires_in_days"], 7)

    def test_customer_cannot_generate_share_link(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            f"/api/galleries/{self.gallery_ana.pk}/share-link/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_photographer_cannot_share_others_gallery(self):
        self.api.force_authenticate(self.beto)
        response = self.api.post(
            f"/api/galleries/{self.gallery_ana.pk}/share-link/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_opens_valid_link(self):
        data = self._share()
        anonymous = APIClient()
        response = anonymous.get(data["url"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["gallery"]["id"], self.gallery_ana.pk)
        self.assertEqual(len(response.data["photos"]), 1)
        self.assertEqual(
            response.data["photos"][0]["image"], "https://example.com/foto1.jpg"
        )

    def test_tampered_token_is_rejected(self):
        response = self.api.get("/api/gallery-view/abc123/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("no es válido", str(response.data))

    @override_settings(GALLERY_SHARE_MAX_AGE=-1)
    def test_expired_link_is_rejected(self):
        data = self._share()
        anonymous = APIClient()
        response = anonymous.get(data["url"])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("expirado", str(response.data))

    def test_deleted_gallery_link_stops_working(self):
        data = self._share()
        self.gallery_ana.delete()
        anonymous = APIClient()
        response = anonymous.get(data["url"])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_client_without_user_does_not_break_link(self):
        manual_client = Client.objects.create(
            photographer=self.ana, name="Sin cuenta"
        )
        manual_shoot = Shoot.objects.create(
            client=manual_client,
            title="Sesion manual",
            shoot_type="retrato",
            date="2026-12-05T10:00:00Z",
        )
        manual_gallery = Gallery.objects.create(shoot=manual_shoot)
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/galleries/{manual_gallery.pk}/share-link/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        anonymous = APIClient()
        response = anonymous.get(response.data["url"])
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["gallery"]["client_username"])
