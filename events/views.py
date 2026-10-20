
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.db import transaction

from .models import Event, Reservation
from .serializers import EventSerializer, ReservationSerializer


class EventViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = EventSerializer

    def get_queryset(self):
        queryset = Event.objects.all()

        event_status = self.request.query_params.get('status')
        venue = self.request.query_params.get('venue')

        if event_status:
            queryset = queryset.filter(status=event_status)

        if venue:
            queryset = queryset.filter(venue__icontains=venue)

        return queryset


class ReservationViewSet(viewsets.ModelViewSet):
    queryset = Reservation.objects.all()
    serializer_class = ReservationSerializer

    def get_queryset(self):
        queryset = Reservation.objects.all()
        event_id = self.request.query_params.get('event_id')

        if event_id:
            queryset = queryset.filter(event_id=event_id)

        return queryset

    def perform_create(self, serializer):
        seats_requested = serializer.validated_data['seats_reserved']
        event_requested = serializer.validated_data['event']

        with transaction.atomic():
            event_requested = Event.objects.select_for_update().get(
                pk=event_requested.pk
            )

            if event_requested.available_seats < seats_requested:
                raise ValidationError("Not Enough Seats Available")

            event_requested.available_seats -= seats_requested
            event_requested.save()
            serializer.save(event=event_requested)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        with transaction.atomic():
            reservation = self.get_object()

            if reservation.status == 'cancelled':
                return Response(
                    {"message": "Reservation already cancelled"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            event = Event.objects.select_for_update().get(
                pk=reservation.event_id
            )
            event.available_seats += reservation.seats_reserved
            event.save()

            reservation.status = 'cancelled'
            reservation.save()

        return Response(
            ReservationSerializer(reservation).data,
            status=status.HTTP_200_OK
        )
