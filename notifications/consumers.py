from urllib.parse import parse_qs

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    """One open line per user: the server pushes new notifications here."""

    async def connect(self):
        user = await sync_to_async(self._authenticate)()
        if user is None:
            await self.close()
            return
        self.group_name = f"notifications_{user.pk}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(
                group_name, self.channel_name
            )

    async def notification_event(self, event):
        """Deliver messages with type "notification.event" to the client."""
        await self.send_json(event["payload"])

    def _authenticate(self):
        # Session login first (browsers, admin tests).
        user = self.scope.get("user")
        if user is not None and user.is_authenticated:
            return user
        # JWT in the query string: ws://host/ws/notifications/?token=ACCESS
        query = parse_qs(self.scope.get("query_string", b"").decode())
        token = (query.get("token") or [None])[0]
        if not token:
            return None
        try:
            validated = AccessToken(token)
            return JWTAuthentication().get_user(validated)
        except (InvalidToken, TokenError):
            return None
