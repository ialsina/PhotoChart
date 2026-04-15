"""API views for the catalog app."""

from rest_framework import viewsets
from .models import Checksum, Directory, DirKind, Location, TimeLoc
from .serializers import (
    ChecksumSerializer,
    DirectorySerializer,
    DirKindSerializer,
    LocationSerializer,
    TimeLocSerializer,
)


class ChecksumViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing Checksum instances."""

    queryset = Checksum.objects.all()
    serializer_class = ChecksumSerializer


class HashViewSet(ChecksumViewSet):
    """Backward-compatible alias for ChecksumViewSet."""


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
