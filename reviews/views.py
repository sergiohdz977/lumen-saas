from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from users.models import User
from users.permissions import IsCustomer, IsPhotographer
from notifications.services import notify
from .models import Review
from .serializers import ReviewSerializer


class ReviewViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Reviews are written once per completed session and never edited.

    The photographer answers with a single public reply.
    """

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    queryset = Review.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        if self.action == "reply":
            return [IsAuthenticated(), IsPhotographer()]
        return [IsAuthenticated(), IsCustomer()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Review.objects.none()
        qs = Review.objects.select_related(
            "photographer", "customer", "photographer__profile", "booking"
        )
        photographer_id = self.request.query_params.get("photographer")
        if photographer_id:
            return qs.filter(photographer_id=photographer_id)
        if user.role == User.ROLE_CUSTOMER:
            return qs.filter(customer=user)
        return qs.filter(photographer=user)

    def perform_create(self, serializer):
        review = serializer.save(customer=self.request.user)
        notify(
            review.photographer,
            "New review",
            f"{review.customer.username} gave you {review.rating}/5",
            link="dashboard.html?tab=reviews",
        )

    @action(detail=True, methods=["post"])
    def reply(self, request, pk=None):
        """Photographer answers a review — publicly, and only once."""
        review = self.get_object()
        if review.photographer_id != request.user.id:
            raise PermissionDenied("You can only reply to your own reviews")
        if review.reply:
            raise ValidationError("You have already replied to this review")
        text = str(request.data.get("reply", "")).strip()
        if not text:
            raise ValidationError("The reply cannot be empty")
        if len(text) > 500:
            raise ValidationError("The reply cannot exceed 500 characters")
        review.reply = text
        review.replied_at = timezone.now()
        review.save(update_fields=["reply", "replied_at"])
        notify(
            review.customer,
            "Reply to your review",
            f"{review.photographer.username} replied to your review: "
            f"{text[:120]}",
            link="dashboard.html?tab=reviews",
        )
        return Response(self.get_serializer(review).data)
