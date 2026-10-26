from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import FileResponse, Http404
from django.urls import include, path, re_path
from django.views.static import serve as serve_static_file
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

FRONTEND_DIR = settings.BASE_DIR / "frontend"


def page(filename):
    def view(request, *args, **kwargs):
        file_path = FRONTEND_DIR / filename
        if not file_path.is_file():
            raise Http404
        response = FileResponse(
            open(file_path, "rb"),
            content_type="text/html; charset=utf-8",
        )
        response["Cache-Control"] = "no-store"
        return response

    return view


def frontend_asset(request, path):
    response = serve_static_file(
        request, path, document_root=str(FRONTEND_DIR)
    )
    response["Cache-Control"] = "no-store"
    return response


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("users.urls")),
    path("api/clients/", include("clients.urls")),
    path("api/shoots/", include("shoots.urls")),
    path("api/", include("profiles.urls")),
    path("api/", include("bookings.urls")),
    path("api/", include("galleries.urls")),
    path("api/", include("reviews.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("payments.urls")),
    # API documentation (OpenAPI schema + Swagger UI).
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("", page("index.html"), name="frontend-index"),
    path("index.html", page("index.html")),
    path("dashboard.html", page("dashboard.html"), name="frontend-dashboard"),
    path("profile.html", page("profile.html"), name="frontend-profile"),
    re_path(
        r"^(?P<path>(?:css|js|img)/[A-Za-z0-9._/-]+)$",
        frontend_asset,
        name="frontend-assets",
    ),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    )
