from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from users.models import User
from users.permissions import IsCustomer
from notifications.services import notify
from .models import Review
from .serializers import ReviewSerializer


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    queryset = Review.objects.all()

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsCustomer()]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Review.objects.none()
        qs = Review.objects.select_related("photographer", "customer")
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
            "Nueva valoracion",
            f"{review.customer.username} te puso {review.rating}/5",
        )
