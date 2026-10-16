from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification


def notify(user, title, message=""):
    """Persist a notification and push it over the open WebSocket.

    Called from synchronous code (views, Celery tasks). The push is
    best-effort: the row is saved even if no WebSocket or no Redis is
    available, so the REST endpoint always shows the full history.
    """
    notification = Notification.objects.create(
        user=user, title=title, message=message
    )
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return notification
    try:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{user.pk}",
            {
                "type": "notification.event",
                "payload": {
                    "id": notification.pk,
                    "title": notification.title,
                    "message": notification.message,
                    "created_at": notification.created_at.isoformat(),
                },
            },
        )
    except Exception:
        # No broker or no open sockets: nothing is lost, the row exists.
        pass
    return notification
