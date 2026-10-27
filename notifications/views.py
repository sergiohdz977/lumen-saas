from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """The logged-in user only sees and manages their own notifications."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Notification.objects.none()
        qs = Notification.objects.filter(user=user)
        # `?unread=1` powers the unread badge in the web dashboard.
        if self.request.query_params.get("unread") == "1":
            qs = qs.filter(is_read=False)
        return qs

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        updated = self.get_queryset().filter(is_read=False).update(
            is_read=True
        )
        return Response({"updated": updated})
