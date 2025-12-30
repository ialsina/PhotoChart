"""API views for the album app."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .models import Album
from .serializers import AlbumSerializer


class AlbumViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Album instances."""

    queryset = Album.objects.all().prefetch_related("photos")
    serializer_class = AlbumSerializer

    @action(detail=True, methods=["post"])
    def add_photos(self, request, pk=None):
        """Add photos to an album."""
        album = self.get_object()
        photo_ids = request.data.get("photo_ids", [])

        if not isinstance(photo_ids, list):
            return Response(
                {"error": "photo_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from photograph.models import Photograph

        photos = Photograph.objects.filter(id__in=photo_ids)
        album.photos.add(*photos)

        return Response({"status": "success", "added_count": len(photo_ids)})

    @action(detail=True, methods=["post"])
    def remove_photos(self, request, pk=None):
        """Remove photos from an album."""
        album = self.get_object()
        photo_ids = request.data.get("photo_ids", [])

        if not isinstance(photo_ids, list):
            return Response(
                {"error": "photo_ids must be a list"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from photograph.models import Photograph

        photos = Photograph.objects.filter(id__in=photo_ids)
        album.photos.remove(*photos)

        return Response({"status": "success", "removed_count": len(photo_ids)})
