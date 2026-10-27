from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient
from rest_framework import status

from bookings.models import BookingRequest
from clients.models import Client
from notifications.models import Notification
from payments.models import Payment
from profiles.models import Package, PhotographerProfile
from shoots.models import Shoot
from users.models import User
from .models import Favorite, Gallery, Photo
from .tasks import generate_photo_variants


def fake_image(name="foto.jpg", size=(1600, 1200)):
    buffer = BytesIO()
    Image.new("RGB", size, (180, 40, 40)).save(buffer, format="JPEG")
    return SimpleUploadedFile(
        name, buffer.getvalue(), content_type="image/jpeg"
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
        self.assertIn("does not belong", str(response.data))

    def test_shoot_can_have_only_one_gallery(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/galleries/", {"shoot": self.shoot_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already has a gallery", str(response.data))

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

    def test_list_includes_photo_count(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/galleries/")
        self.assertEqual(response.data["results"][0]["photo_count"], 1)

    def test_detail_includes_photo_count(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["photo_count"], 1)

    def test_gallery_without_photos_reports_zero(self):
        self.api.force_authenticate(self.beto)
        self.api.post(
            "/api/galleries/", {"shoot": self.shoot_beto.pk}, format="json"
        )
        response = self.api.get("/api/galleries/")
        counts = [item["photo_count"] for item in response.data["results"]]
        self.assertIn(0, counts)

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
        self.assertIn("not valid", str(response.data))

    @override_settings(GALLERY_SHARE_MAX_AGE=-1)
    def test_expired_link_is_rejected(self):
        data = self._share()
        anonymous = APIClient()
        response = anonymous.get(data["url"])
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("expired", str(response.data))

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


class ThumbnailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
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

    def setUp(self):
        self.api = APIClient()

    def _upload(self, image=None):
        self.api.force_authenticate(self.ana)
        return self.api.post(
            "/api/photos/",
            {"gallery": self.gallery_ana.pk, "image": image or fake_image()},
            format="multipart",
        )

    def _variant_path(self, url):
        relative = url.removeprefix(settings.MEDIA_URL)
        return Path(settings.MEDIA_ROOT) / relative

    def _thumbnail_path(self, photo):
        return self._variant_path(photo.thumbnail)

    def test_upload_generates_thumbnail_in_background(self):
        response = self._upload()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("thumbnail", response.data)
        photo = Photo.objects.get(pk=response.data["id"])
        self.assertTrue(photo.thumbnail)
        self.assertTrue(photo.thumbnail.startswith("/media/"))
        self.assertTrue(self._thumbnail_path(photo).exists())

    def test_upload_generates_hd_preview(self):
        response = self._upload()
        photo = Photo.objects.get(pk=response.data["id"])
        self.assertTrue(photo.preview)
        self.assertTrue(self._variant_path(photo.preview).exists())
        with Image.open(self._variant_path(photo.preview)) as preview:
            self.assertEqual(preview.format, "JPEG")
            self.assertEqual(preview.width, 1280)
            self.assertEqual(preview.height, 960)

    def test_thumbnail_is_resized_to_max_width_400(self):
        response = self._upload()
        photo = Photo.objects.get(pk=response.data["id"])
        with Image.open(self._thumbnail_path(photo)) as thumb:
            self.assertEqual(thumb.format, "JPEG")
            self.assertEqual(thumb.width, 400)
            self.assertEqual(thumb.height, 300)

    def test_replacing_image_regenerates_thumbnail(self):
        response = self._upload()
        photo = Photo.objects.get(pk=response.data["id"])
        old_thumbnail = photo.thumbnail
        self.api.force_authenticate(self.ana)
        patch = self.api.patch(
            f"/api/photos/{photo.pk}/",
            {"image": fake_image("otra.jpg")},
            format="multipart",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        photo.refresh_from_db()
        self.assertTrue(photo.thumbnail)
        self.assertNotEqual(photo.thumbnail, old_thumbnail)
        with Image.open(self._thumbnail_path(photo)) as thumb:
            self.assertEqual(thumb.width, 400)

    def test_caption_update_keeps_thumbnail(self):
        response = self._upload()
        photo = Photo.objects.get(pk=response.data["id"])
        old_thumbnail = photo.thumbnail
        self.api.force_authenticate(self.ana)
        patch = self.api.patch(
            f"/api/photos/{photo.pk}/",
            {"caption": "Solo texto"},
            format="json",
        )
        self.assertEqual(patch.status_code, status.HTTP_200_OK)
        photo.refresh_from_db()
        self.assertEqual(photo.thumbnail, old_thumbnail)
        self.assertEqual(photo.caption, "Solo texto")

    def test_broken_image_still_uploads_without_thumbnail(self):
        response = self._upload(
            SimpleUploadedFile(
                "rota.jpg", b"\xff\xd8\xff\xe0esto no es jpeg",
                content_type="image/jpeg",
            )
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        photo = Photo.objects.get(pk=response.data["id"])
        self.assertEqual(photo.thumbnail, "")

    def test_task_ignores_missing_photo(self):
        self.assertIsNone(generate_photo_variants(99999))


class GalleryDeliveryEmailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
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

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.ana)

    def _create_gallery(self, shoot):
        return self.api.post(
            "/api/galleries/", {"shoot": shoot.pk}, format="json"
        )

    def test_gallery_creation_emails_customer_with_share_link(self):
        response = self._create_gallery(self.shoot_ana)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Your photos are ready")
        self.assertEqual(mail.outbox[0].to, ["maria@test.com"])
        self.assertIn("/api/gallery-view/", mail.outbox[0].body)

    def test_manual_client_with_email_gets_delivery_email(self):
        manual = Client.objects.create(
            photographer=self.ana, name="Manual", email="manual@test.com"
        )
        shoot = Shoot.objects.create(
            client=manual,
            title="Sesion manual",
            shoot_type="retrato",
            date="2026-12-05T10:00:00Z",
        )
        response = self._create_gallery(shoot)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["manual@test.com"])

    def test_client_without_any_email_sends_nothing(self):
        manual = Client.objects.create(photographer=self.ana, name="Sin mail")
        shoot = Shoot.objects.create(
            client=manual,
            title="Sesion sin mail",
            shoot_type="retrato",
            date="2026-12-06T10:00:00Z",
        )
        response = self._create_gallery(shoot)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(mail.outbox), 0)


class FavoritesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
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

    def test_customer_favorites_a_photo(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Favorite.objects.count(), 1)

    def test_photographer_cannot_favorite(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_favorite(self):
        response = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_cannot_favorite_same_photo_twice(self):
        self.api.force_authenticate(self.maria)
        self.api.post("/api/favorites/", {"photo": self.photo_ana.pk})
        response = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already", str(response.data))

    def test_cannot_favorite_another_customers_photo(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot", str(response.data))

    def test_customer_lists_only_own_favorites(self):
        self.api.force_authenticate(self.maria)
        self.api.post("/api/favorites/", {"photo": self.photo_ana.pk})
        response = self.api.get("/api/favorites/")
        self.assertEqual(response.data["count"], 1)
        self.api.force_authenticate(self.luis)
        response = self.api.get("/api/favorites/")
        self.assertEqual(response.data["count"], 0)

    def test_customer_removes_own_favorite(self):
        self.api.force_authenticate(self.maria)
        created = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        response = self.api.delete(f"/api/favorites/{created.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_cannot_delete_others_favorite(self):
        self.api.force_authenticate(self.maria)
        created = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.api.force_authenticate(self.luis)
        response = self.api.delete(f"/api/favorites/{created.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_favoriting_notifies_the_photographer(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        notification = Notification.objects.get(user=self.ana)
        self.assertEqual(notification.title, "New favorite")
        self.assertIn("maria", notification.message)
        self.assertIn("Boda de Maria", notification.message)

    def test_favorite_notification_is_not_sent_to_the_customer(self):
        self.api.force_authenticate(self.maria)
        self.api.post("/api/favorites/", {"photo": self.photo_ana.pk})
        self.assertFalse(
            Notification.objects.filter(user=self.maria).exists()
        )

    def test_unfavorite_does_not_create_a_notification(self):
        self.api.force_authenticate(self.maria)
        created = self.api.post(
            "/api/favorites/", {"photo": self.photo_ana.pk}, format="json"
        )
        self.assertEqual(Notification.objects.count(), 1)
        response = self.api.delete(f"/api/favorites/{created.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Notification.objects.count(), 1)


class PhotographerFavoriteVisibilityTests(TestCase):
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
        cls.gallery_beto = Gallery.objects.create(shoot=cls.shoot_beto)
        cls.photo_ana = Photo.objects.create(
            gallery=cls.gallery_ana,
            image="https://example.com/foto-ana.jpg",
            thumbnail="https://example.com/thumb-ana.jpg",
            caption="Ceremonia",
        )
        cls.photo_beto = Photo.objects.create(
            gallery=cls.gallery_beto,
            image="https://example.com/foto-beto.jpg",
        )

    def setUp(self):
        self.api = APIClient()

    def _favorite(self, user, photo):
        self.api.force_authenticate(user)
        return self.api.post(
            "/api/favorites/", {"photo": photo.pk}, format="json"
        )

    def test_photographer_sees_client_favorites_with_details(self):
        self._favorite(self.maria, self.photo_ana)
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/favorites/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        item = response.data["results"][0]
        self.assertEqual(item["customer_username"], "maria")
        self.assertEqual(item["photo_caption"], "Ceremonia")
        self.assertEqual(
            item["photo_thumbnail"], "https://example.com/thumb-ana.jpg"
        )

    def test_photographer_does_not_see_other_photographers_favorites(self):
        self._favorite(self.pedro, self.photo_beto)
        self.api.force_authenticate(self.ana)
        response = self.api.get("/api/favorites/")
        self.assertEqual(response.data["count"], 0)

    def test_photographer_cannot_delete_clients_favorite(self):
        created = self._favorite(self.maria, self.photo_ana)
        self.api.force_authenticate(self.ana)
        response = self.api.delete(f"/api/favorites/{created.data['id']}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_list_includes_thumbnail(self):
        self._favorite(self.maria, self.photo_ana)
        self.api.force_authenticate(self.maria)
        response = self.api.get("/api/favorites/")
        self.assertEqual(
            response.data["results"][0]["photo_thumbnail"],
            "https://example.com/thumb-ana.jpg",
        )

    def test_list_filter_by_photo(self):
        self._favorite(self.maria, self.photo_ana)
        self.api.force_authenticate(self.ana)
        response = self.api.get(f"/api/favorites/?photo={self.photo_ana.pk}")
        self.assertEqual(response.data["count"], 1)
        response = self.api.get(f"/api/favorites/?photo={self.photo_beto.pk}")
        self.assertEqual(response.data["count"], 0)


class PhotoDownloadTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
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
        )

    def setUp(self):
        self.api = APIClient()

    def test_customer_registers_download(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["download_count"], 1)
        self.assertEqual(response.data["light_download_count"], 0)

    def test_light_and_original_downloads_count_separately(self):
        self.api.force_authenticate(self.maria)
        self.api.post(
            f"/api/photos/{self.photo_ana.pk}/download/",
            {"version": "light"},
            format="json",
        )
        self.api.post(
            f"/api/photos/{self.photo_ana.pk}/download/",
            {"version": "light"},
            format="json",
        )
        response = self.api.post(
            f"/api/photos/{self.photo_ana.pk}/download/",
            {"version": "original"},
            format="json",
        )
        self.assertEqual(response.data["light_download_count"], 2)
        self.assertEqual(response.data["download_count"], 1)
        self.photo_ana.refresh_from_db()
        self.assertEqual(self.photo_ana.light_download_count, 2)
        self.assertEqual(self.photo_ana.download_count, 1)

    def test_invalid_download_version_is_rejected(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            f"/api/photos/{self.photo_ana.pk}/download/",
            {"version": "gold"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid version", str(response.data))

    def test_downloads_accumulate(self):
        self.api.force_authenticate(self.maria)
        self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.data["download_count"], 2)
        self.photo_ana.refresh_from_db()
        self.assertEqual(self.photo_ana.download_count, 2)

    def test_photographer_can_register_download(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["download_count"], 1)

    def test_other_customer_cannot_register_download(self):
        self.api.force_authenticate(self.luis)
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_download_is_denied(self):
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


class UploadPermissionAuditTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
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

    def setUp(self):
        self.api = APIClient()

    def test_anonymous_upload_is_denied(self):
        response = self.api.post(
            "/api/photos/",
            {"gallery": self.gallery_ana.pk, "image": fake_image()},
            format="multipart",
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_upload_requires_gallery_field(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/", {"image": fake_image()}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("gallery", response.data)

    def test_upload_with_unknown_gallery_is_rejected(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/",
            {"gallery": 9999, "image": fake_image()},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Photo.objects.count(), 0)

    def test_empty_file_is_rejected_in_spanish(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/",
            {
                "gallery": self.gallery_ana.pk,
                "image": SimpleUploadedFile(
                    "vacia.jpg", b"", content_type="image/jpeg"
                ),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("empty", str(response.data))

    def test_missing_image_message_is_in_spanish(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/", {"gallery": self.gallery_ana.pk}, format="multipart"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("required", str(response.data))

    def test_gallery_create_with_unknown_shoot_is_rejected(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/galleries/", {"shoot": 9999}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_favorite_with_unknown_photo_is_rejected(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            "/api/favorites/", {"photo": 9999}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Favorite.objects.count(), 0)

    def test_download_unknown_photo_returns_404(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post("/api/photos/9999/download/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_anonymous_share_link_is_denied(self):
        response = self.api.post(
            f"/api/galleries/{self.gallery_ana.pk}/share-link/"
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )


class PlanLimitTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
            password="secret123",
            role=User.ROLE_PHOTOGRAPHER,
        )
        cls.maria = User.objects.create_user(
            username="maria",
            email="maria@test.com",
            password="secret123",
            role=User.ROLE_CUSTOMER,
        )
        cls.profile = PhotographerProfile.objects.create(
            user=cls.ana,
            studio_name="Ana Studio",
            slug="ana-studio",
        )
        cls.client_maria = Client.objects.create(
            photographer=cls.ana, user=cls.maria, name="Maria F"
        )
        cls.shoot_1 = Shoot.objects.create(
            client=cls.client_maria,
            title="Boda de Maria",
            shoot_type="boda",
            date="2026-11-20T10:00:00Z",
        )
        cls.shoot_2 = Shoot.objects.create(
            client=cls.client_maria,
            title="Preboda de Maria",
            shoot_type="preboda",
            date="2026-11-19T10:00:00Z",
        )
        cls.gallery_1 = Gallery.objects.create(shoot=cls.shoot_1)
        cls.photo_1 = Photo.objects.create(
            gallery=cls.gallery_1,
            image="https://example.com/foto1.jpg",
            caption="Primera",
        )

    def setUp(self):
        self.api = APIClient()

    @override_settings(FREE_TIER_GALLERIES=1)
    def test_free_plan_is_limited_to_the_gallery_quota(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/galleries/", {"shoot": self.shoot_2.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Free plan", str(response.data))
        self.assertFalse(
            Gallery.objects.filter(shoot=self.shoot_2).exists()
        )

    @override_settings(FREE_TIER_GALLERIES=1)
    def test_pro_plan_has_unlimited_galleries(self):
        self.profile.plan = "pro"
        self.profile.save(update_fields=["plan"])
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/galleries/", {"shoot": self.shoot_2.pk}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @override_settings(FREE_TIER_PHOTOS=1)
    def test_free_plan_is_limited_to_the_photo_quota(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/",
            {
                "gallery": self.gallery_1.pk,
                "image": fake_image("nueva.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Free plan", str(response.data))
        self.assertEqual(Photo.objects.count(), 1)

    @override_settings(FREE_TIER_PHOTOS=1)
    def test_pro_plan_has_unlimited_photos(self):
        self.profile.plan = "pro"
        self.profile.save(update_fields=["plan"])
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            "/api/photos/",
            {
                "gallery": self.gallery_1.pk,
                "image": fake_image("nueva.jpg"),
            },
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class PaymentGateTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = User.objects.create_user(
            username="ana",
            email="ana@test.com",
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
        cls.package = Package.objects.create(
            profile=cls.ana_profile, title="Boda completa", price=200
        )
        cls.client_maria = Client.objects.create(
            photographer=cls.ana, user=cls.maria, name="Maria F"
        )
        cls.booking = BookingRequest.objects.create(
            customer=cls.maria,
            package=cls.package,
            date="2026-11-20T10:00:00Z",
            status=BookingRequest.Status.ACCEPTED_PENDING_DEPOSIT,
        )
        cls.shoot_ana = Shoot.objects.create(
            client=cls.client_maria,
            title="Boda de Maria",
            shoot_type="boda",
            date="2026-11-20T10:00:00Z",
            booking=cls.booking,
        )
        cls.gallery_ana = Gallery.objects.create(shoot=cls.shoot_ana)
        cls.photo_ana = Photo.objects.create(
            gallery=cls.gallery_ana,
            image="https://example.com/original1.jpg",
            preview="https://example.com/preview1.jpg",
            thumbnail="https://example.com/thumb1.jpg",
        )

    def setUp(self):
        self.api = APIClient()

    def _pay(self, kind, stripe_id):
        Payment.objects.create(
            booking=self.booking,
            kind=kind,
            customer=self.maria,
            photographer=self.ana,
            amount_cents=4000 if kind == Payment.Kind.DEPOSIT else 16000,
            stripe_session_id=stripe_id,
            status=Payment.Status.PAID,
        )

    def _pay_all(self):
        self._pay(Payment.Kind.DEPOSIT, "cs_gate_dep")
        self._pay(Payment.Kind.BALANCE, "cs_gate_bal")

    def test_customer_high_res_download_blocked_before_payment(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("high quality", str(response.data))

    def test_customer_light_download_allowed_before_payment(self):
        self.api.force_authenticate(self.maria)
        response = self.api.post(
            f"/api/photos/{self.photo_ana.pk}/download/",
            {"version": "light"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_deposit_alone_does_not_unlock_high_res(self):
        self._pay(Payment.Kind.DEPOSIT, "cs_gate_dep")
        self.api.force_authenticate(self.maria)
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_full_payment_unlocks_high_res(self):
        self._pay_all()
        self.api.force_authenticate(self.maria)
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["download_count"], 1)

    def test_photographer_high_res_allowed_before_payment(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(f"/api/photos/{self.photo_ana.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unpaid_customer_sees_masked_image(self):
        self.api.force_authenticate(self.maria)
        response = self.api.get(f"/api/photos/{self.photo_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["image"], "https://example.com/preview1.jpg"
        )

    def test_fully_paid_customer_sees_original_image(self):
        self._pay_all()
        self.api.force_authenticate(self.maria)
        response = self.api.get(f"/api/photos/{self.photo_ana.pk}/")
        self.assertEqual(
            response.data["image"], "https://example.com/original1.jpg"
        )

    def test_photographer_always_sees_original_image(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get(f"/api/photos/{self.photo_ana.pk}/")
        self.assertEqual(
            response.data["image"], "https://example.com/original1.jpg"
        )

    def test_gallery_flags_show_awaiting_deposit(self):
        self.api.force_authenticate(self.maria)
        response = self.api.get(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["booking_status"], "accepted_pending_deposit"
        )
        self.assertFalse(response.data["fully_paid"])

    def test_gallery_flag_fully_paid_after_balance(self):
        self._pay_all()
        self.api.force_authenticate(self.maria)
        response = self.api.get(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertTrue(response.data["fully_paid"])

    def test_photographer_gallery_flag_is_fully_paid(self):
        self.api.force_authenticate(self.ana)
        response = self.api.get(f"/api/galleries/{self.gallery_ana.pk}/")
        self.assertTrue(response.data["fully_paid"])

    def _share_token(self):
        self.api.force_authenticate(self.ana)
        response = self.api.post(
            f"/api/galleries/{self.gallery_ana.pk}/share-link/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data["url"].rstrip("/").rsplit("/", 1)[-1]

    def test_share_view_masks_image_for_anonymous_visitor(self):
        token = self._share_token()
        anon = APIClient()
        response = anon.get(f"/api/gallery-view/{token}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["gallery"]["fully_paid"])
        self.assertEqual(
            response.data["photos"][0]["image"],
            "https://example.com/preview1.jpg",
        )

    def test_share_view_shows_original_after_full_payment(self):
        self._pay_all()
        token = self._share_token()
        anon = APIClient()
        response = anon.get(f"/api/gallery-view/{token}/")
        self.assertTrue(response.data["gallery"]["fully_paid"])
        self.assertEqual(
            response.data["photos"][0]["image"],
            "https://example.com/original1.jpg",
        )
