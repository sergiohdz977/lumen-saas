from datetime import timedelta
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from clients.models import Client
from notifications.services import notify
from payments.models import Payment
from shoots.models import Shoot
from users.models import User
from users.permissions import IsCustomer, IsPhotographer

from .models import BookingRequest, Message
from .serializers import BookingRequestSerializer, MessageSerializer
from .tasks import booking_accepted_email, enforce_deposit_deadline


def _booking_link(booking):
    return f"dashboard.html?tab=requests&item={booking.pk}"


def ensure_shoot_and_client(booking):
    """Create the shoot + client rows for this booking (idempotent).

    Raises ValidationError when the photographer already has a shoot
    booked on that day.
    """
    photographer = booking.package.profile.user
    with transaction.atomic():
        try:
            if booking.shoot is not None:
                return booking.shoot
        except ObjectDoesNotExist:  # pragma: no cover - reverse one-to-one
            pass
        has_conflict = (
            Shoot.objects.filter(
                client__photographer=photographer,
                date__date=booking.date.date(),
            )
            # Cancelled bookings keep their shoot only when a gallery hangs
            # off it, so their date must not block new bookings.
            .exclude(booking__status=BookingRequest.Status.CANCELLED)
            .exists()
        )
        if has_conflict:
            raise ValidationError("You already have a shoot booked that day")
        client, _ = Client.objects.get_or_create(
            photographer=photographer,
            user=booking.customer,
            defaults={
                "name": (
                    booking.customer.get_full_name()
                    or booking.customer.username
                ),
                "email": booking.customer.email,
                "phone": "",
            },
        )
        return Shoot.objects.create(
            client=client,
            title=f"{booking.package.title} - {booking.customer.username}",
            shoot_type=booking.package.title,
            date=booking.date,
            booking=booking,
        )


class BookingRequestViewSet(viewsets.ModelViewSet):
    serializer_class = BookingRequestSerializer
    queryset = BookingRequest.objects.all()

    def get_permissions(self):
        if self.action == "create":
            return [IsAuthenticated(), IsCustomer()]
        if self.action in (
            "accept",
            "reject",
            "offer",
            "pay_cash",
            "complete",
        ):
            return [IsAuthenticated(), IsPhotographer()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = BookingRequest.objects.select_related(
            "package__profile", "customer"
        )
        if not user.is_authenticated:
            return qs.none()
        if user.role == User.ROLE_CUSTOMER:
            return qs.filter(customer=user)
        return qs.filter(package__profile__user=user)

    def perform_create(self, serializer):
        # New bookings always start at REQUESTED: no Stripe involved yet.
        booking = serializer.save(
            customer=self.request.user,
            status=BookingRequest.Status.REQUESTED,
        )
        notify(
            booking.package.profile.user,
            "New booking request",
            f'"{booking.customer.username}" wants to book '
            f'"{booking.package.title}" for {booking.date:%d/%m/%Y}',
            link=_booking_link(booking),
        )

    # ----------------------------- negotiation -----------------------------

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Photographer accepts the request as-is (current price)."""
        return self._send_offer(request, price=None)

    @action(detail=True, methods=["post"])
    def offer(self, request, pk=None):
        """Photographer sends a customized price (custom offer)."""
        raw = request.data.get("final_price")
        try:
            price = Decimal(str(raw)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            raise ValidationError("final_price must be a number")
        if price <= 0:
            raise ValidationError("final_price must be greater than zero")
        return self._send_offer(request, price=price)

    def _send_offer(self, request, price):
        booking = self.get_object()
        if booking.status not in (
            BookingRequest.Status.REQUESTED,
            BookingRequest.Status.AWAITING_PAYMENT,
        ):
            raise ValidationError(
                "Only requested bookings can be negotiated"
            )
        first_time = booking.status == BookingRequest.Status.REQUESTED
        schedule_deadline = False
        with transaction.atomic():
            if price is not None:
                booking.final_price = price
            ensure_shoot_and_client(booking)
            booking.status = BookingRequest.Status.AWAITING_PAYMENT
            fields = ["status"]
            if price is not None:
                fields.append("final_price")
            if booking.deposit_deadline is None:
                booking.deposit_deadline = timezone.now() + timedelta(
                    hours=settings.DEPOSIT_DEADLINE_HOURS
                )
                fields.append("deposit_deadline")
                schedule_deadline = True
            booking.save(update_fields=fields)
            if schedule_deadline:
                deadline = booking.deposit_deadline
                transaction.on_commit(
                    lambda: enforce_deposit_deadline.apply_async(
                        (booking.pk,), eta=deadline
                    )
                )
        if first_time:
            booking_accepted_email.delay(booking.pk)
        Message.objects.create(
            booking=booking,
            sender=None,
            text=(
                "The photographer accepted your request. Pay the deposit "
                "to confirm the booking."
                if price is None
                else f"Custom offer sent: the final price is now "
                f"${price:.2f}. Pay the deposit to confirm the booking."
            ),
        )
        if price is None:
            notify(
                booking.customer,
                "Booking accepted",
                (
                    f'Your booking for "{booking.package.title}" was '
                    f"accepted. Pay the deposit within "
                    f"{settings.DEPOSIT_DEADLINE_HOURS} hours to confirm it."
                ),
                link=_booking_link(booking),
            )
        else:
            notify(
                booking.customer,
                "New offer",
                (
                    f'"{booking.package.profile.studio_name or request.user.username}" '
                    f"sent you an offer of ${price:.2f} for "
                    f'"{booking.package.title}". Pay the deposit to confirm.'
                ),
                link=_booking_link(booking),
            )
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def pay_cash(self, request, pk=None):
        """Mark the booking as paid in cash: ACCEPTED, money in earnings."""
        booking = self.get_object()
        if booking.status not in (
            BookingRequest.Status.REQUESTED,
            BookingRequest.Status.AWAITING_PAYMENT,
        ):
            raise ValidationError(
                "Only bookings waiting for payment can be marked as paid"
            )
        amount = booking.effective_price
        with transaction.atomic():
            ensure_shoot_and_client(booking)
            booking.status = BookingRequest.Status.ACCEPTED
            booking.save(update_fields=["status"])
            if not Payment.objects.filter(
                booking=booking, kind=Payment.Kind.CASH
            ).exists():
                Payment.objects.create(
                    booking=booking,
                    kind=Payment.Kind.CASH,
                    customer=booking.customer,
                    photographer=booking.package.profile.user,
                    amount_cents=int(
                        (amount * 100).quantize(Decimal("1"))
                    ),
                    status=Payment.Status.PAID,
                    stripe_session_id=f"cash_{uuid4().hex[:32]}",
                    paid_at=timezone.now(),
                )
        Message.objects.create(
            booking=booking,
            sender=None,
            text=(
                "Payment received in cash. The booking is confirmed "
                "and the gallery can be created."
            ),
        )
        notify(
            booking.customer,
            "Booking confirmed",
            (
                f'Your booking for "{booking.package.title}" was marked '
                "as paid in cash. The photographer can now create the "
                "gallery."
            ),
            link=_booking_link(booking),
        )
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Photographer finishes the job: COMPLETED + ask for a review."""
        booking = self.get_object()
        if booking.status != BookingRequest.Status.ACCEPTED:
            raise ValidationError(
                "Only accepted bookings can be completed"
            )
        booking.status = BookingRequest.Status.COMPLETED
        booking.save(update_fields=["status"])
        Message.objects.create(
            booking=booking,
            sender=None,
            text=(
                "Booking marked as completed. The client can now leave "
                "a review."
            ),
        )
        notify(
            booking.customer,
            "Leave a review",
            (
                f'How was "{booking.package.title}"? Share your '
                "experience with the photographer."
            ),
            link="dashboard.html?tab=reviews",
        )
        return Response(self.get_serializer(booking).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        booking = self.get_object()
        if booking.status not in (
            BookingRequest.Status.REQUESTED,
            BookingRequest.Status.AWAITING_PAYMENT,
        ):
            raise ValidationError("Only pending requests can be managed")
        booking.status = BookingRequest.Status.REJECTED
        booking.save(update_fields=["status"])
        Message.objects.create(
            booking=booking,
            sender=None,
            text="The booking request was rejected.",
        )
        notify(
            booking.customer,
            "Booking rejected",
            (
                f'Your request for "{booking.package.title}" was '
                "declined."
            ),
            link=_booking_link(booking),
        )
        return Response(self.get_serializer(booking).data)

    CANCELABLE_STATUSES = (
        BookingRequest.Status.REQUESTED,
        BookingRequest.Status.AWAITING_PAYMENT,
        BookingRequest.Status.ACCEPTED,
    )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Either party cancels the booking.

        The photographer cancelling always refunds the deposit in full;
        the client follows the 7-day policy (>7 days out: refundable,
        7 or fewer: retained). The freed date is guaranteed by deleting
        the shoot when it has no gallery, and by the CANCELLED exclusion
        in ensure_shoot_and_client when the gallery must survive.
        """
        booking = self.get_object()
        if booking.status not in self.CANCELABLE_STATUSES:
            raise ValidationError("Only active bookings can be cancelled")
        by_photographer = request.user == booking.package.profile.user
        days_left = (booking.date.date() - timezone.now().date()).days
        should_refund = by_photographer or days_left > 7
        had_deposit = booking.payments.filter(
            kind=Payment.Kind.DEPOSIT, status=Payment.Status.PAID
        ).exists()
        refunded_cents = 0
        with transaction.atomic():
            booking.status = BookingRequest.Status.CANCELLED
            booking.save(update_fields=["status"])
            if should_refund:
                for deposit in booking.payments.filter(
                    kind=Payment.Kind.DEPOSIT,
                    status=Payment.Status.PAID,
                ):
                    Payment.objects.create(
                        booking=booking,
                        kind=Payment.Kind.DEPOSIT,
                        customer=deposit.customer,
                        photographer=deposit.photographer,
                        amount_cents=deposit.amount_cents,
                        status=Payment.Status.REFUNDED,
                        stripe_session_id=f"refund_{uuid4().hex[:32]}",
                        paid_at=timezone.now(),
                    )
                    refunded_cents += deposit.amount_cents
            shoot = getattr(booking, "shoot", None)
            if shoot is not None:
                try:
                    shoot.gallery
                except ObjectDoesNotExist:
                    # No gallery attached: drop the shoot to free the date.
                    shoot.delete()
                # With a gallery the shoot must stay (CASCADE would take
                # the gallery with it); the date is freed by the CANCELLED
                # exclusion in the conflict check instead.
        Message.objects.create(
            booking=booking,
            sender=None,
            text=(
                "System: The photographer has cancelled this booking. "
                "The deposit will be refunded."
                if by_photographer
                else "System: The client has cancelled this booking."
            ),
        )
        if by_photographer:
            refund_note = (
                "The deposit will be refunded."
                if refunded_cents
                else "No deposit had been collected."
            )
            notify(
                booking.customer,
                "Booking cancelled",
                f'The photographer cancelled "{booking.package.title}". '
                f"{refund_note}",
                link=_booking_link(booking),
            )
        else:
            if refunded_cents:
                refund_note = "The deposit was refunded."
            elif had_deposit:
                refund_note = "The deposit was retained per the 7-day policy."
            else:
                refund_note = ""
            notify(
                booking.package.profile.user,
                "Booking cancelled",
                f'{booking.customer.username} cancelled '
                f'"{booking.package.title}".'
                + (f" {refund_note}" if refund_note else ""),
                link=_booking_link(booking),
            )
        return Response(self.get_serializer(booking).data)

    # -------------------------------- chat ---------------------------------

    @action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        booking = self.get_object()
        user = request.user
        photographer = booking.package.profile.user
        if user not in (booking.customer, photographer):
            raise PermissionDenied("That booking does not belong to you")
        if request.method == "GET":
            qs = booking.messages.select_related("sender")
            return Response(MessageSerializer(qs, many=True).data)
        text = str(request.data.get("text", "")).strip()
        if not text:
            raise ValidationError("The message cannot be empty")
        message = Message.objects.create(
            booking=booking, sender=user, text=text
        )
        recipient = (
            photographer if user == booking.customer else booking.customer
        )
        notify(
            recipient,
            "New message",
            f"{user.username}: {text[:120]}",
            link=_booking_link(booking),
        )
        return Response(
            MessageSerializer(message).data,
            status=http_status.HTTP_201_CREATED,
        )
