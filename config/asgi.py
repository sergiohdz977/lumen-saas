import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.conf import settings
from django.urls import re_path

from notifications.consumers import NotificationConsumer


class LumenOriginValidator(OriginValidator):
    """Browsers must match ALLOWED_HOSTS (blocks cross-site WebSockets).

    Non-browser clients (tests, mobile apps) send no Origin header;
    they are checked by the JWT auth inside the consumer instead.
    """

    def __init__(self, application):
        allowed_hosts = settings.ALLOWED_HOSTS
        if settings.DEBUG and not allowed_hosts:
            allowed_hosts = ["localhost", "127.0.0.1", "[::1]"]
        super().__init__(application, allowed_hosts)

    def valid_origin(self, parsed_origin):
        if parsed_origin is None:
            return True
        return super().valid_origin(parsed_origin)


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": LumenOriginValidator(
        URLRouter([
            re_path(
                r"ws/notifications/$",
                NotificationConsumer.as_asgi(),
            ),
        ])
    ),
})
