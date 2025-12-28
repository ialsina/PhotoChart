"""API views for the photograph app."""

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Photograph, PhotoPath
from .serializers import PhotographSerializer, PhotoPathSerializer


class PhotographViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Photograph instances."""

    queryset = Photograph.objects.all().prefetch_related("paths")
    serializer_class = PhotographSerializer

    def get_serializer_context(self):
        """Add request to serializer context for image URLs."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @action(detail=True, methods=["post"])
    def compute_hash(self, request, pk=None):
        """Compute hash from the image file."""
        photograph = self.get_object()
        hash_value = photograph.compute_hash_from_image()
        if hash_value:
            return Response({"hash": hash_value, "status": "success"})
        return Response(
            {"status": "error", "message": "Could not compute hash"}, status=400
        )


class PhotoPathViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing PhotoPath instances."""

    queryset = PhotoPath.objects.all().select_related("photograph")
    serializer_class = PhotoPathSerializer
