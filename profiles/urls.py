from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    PhotographerProfileViewSet,
    PackageViewSet,
    PortfolioCollectionViewSet,
    PortfolioPhotoUploadView,
    PortfolioPhotoViewSet,
    ProfileCoverView,
    ProfilePictureView,
)

# Registered before the router so "profiles/picture/", "profiles/cover/"
# and "portfolio-photos/upload/" never match the "{slug}/{pk}/" detail
# routes of the router.
urlpatterns = [
    path(
        "profiles/picture/",
        ProfilePictureView.as_view(),
        name="profile-picture",
    ),
    path(
        "profiles/cover/",
        ProfileCoverView.as_view(),
        name="profile-cover",
    ),
    path(
        "portfolio-photos/upload/",
        PortfolioPhotoUploadView.as_view(),
        name="portfolio-photo-upload",
    ),
]

router = DefaultRouter()
router.register("profiles", PhotographerProfileViewSet, basename="profile")
router.register("packages", PackageViewSet, basename="package")
router.register("portfolio-photos", PortfolioPhotoViewSet, basename="portfolio-photo")
router.register(
    "portfolio-collections",
    PortfolioCollectionViewSet,
    basename="portfolio-collection",
)

urlpatterns += router.urls
