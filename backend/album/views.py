"""API views for the album app."""

from rest_framework import viewsets
from .models import Album
from .serializers import AlbumSerializer


class AlbumViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Album instances."""

    queryset = Album.objects.all().prefetch_related("photos")
    serializer_class = AlbumSerializer
