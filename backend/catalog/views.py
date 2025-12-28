"""API views for the catalog app."""

from rest_framework import viewsets
from .models import Hash, Directory, DirKind, Location, TimeLoc
from .serializers import (
    HashSerializer,
    DirectorySerializer,
    DirKindSerializer,
    LocationSerializer,
    TimeLocSerializer,
)


class HashViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing Hash instances."""

    queryset = Hash.objects.all()
    serializer_class = HashSerializer


class DirectoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing Directory instances."""

    queryset = Directory.objects.all().select_related("kind")
    serializer_class = DirectorySerializer


class DirKindViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing DirKind instances."""

    queryset = DirKind.objects.all()
    serializer_class = DirKindSerializer


class LocationViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing Location instances."""

    queryset = Location.objects.all()
    serializer_class = LocationSerializer


class TimeLocViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing TimeLoc instances."""

    queryset = TimeLoc.objects.all().select_related("path", "location")
    serializer_class = TimeLocSerializer
