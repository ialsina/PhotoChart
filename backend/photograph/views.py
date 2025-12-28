"""API views for the photograph app."""

from datetime import datetime
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Photograph, PhotoPath
from .serializers import PhotographSerializer, PhotoPathSerializer


class PhotographViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing Photograph instances."""

    queryset = Photograph.objects.all().prefetch_related("paths")
    serializer_class = PhotographSerializer

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = super().get_queryset()

        # Filter by year
        year = self.request.query_params.get("year", None)
        if year and year != "Unknown":
            try:
                year_int = int(year)
                start_date = timezone.make_aware(datetime(year_int, 1, 1))
                end_date = timezone.make_aware(datetime(year_int + 1, 1, 1))
                queryset = queryset.filter(time__gte=start_date, time__lt=end_date)
            except (ValueError, TypeError):
                pass

        # Filter by year and month
        month = self.request.query_params.get("month", None)
        if month and year and year != "Unknown":
            try:
                year_int = int(year)
                month_int = int(month)
                start_date = timezone.make_aware(datetime(year_int, month_int, 1))
                if month_int == 12:
                    end_date = timezone.make_aware(datetime(year_int + 1, 1, 1))
                else:
                    end_date = timezone.make_aware(datetime(year_int, month_int + 1, 1))
                queryset = queryset.filter(time__gte=start_date, time__lt=end_date)
            except (ValueError, TypeError):
                pass

        # Filter by year, month, and day
        day = self.request.query_params.get("day", None)
        if day and month and year and year != "Unknown":
            try:
                year_int = int(year)
                month_int = int(month)
                day_int = int(day)
                start_date = timezone.make_aware(datetime(year_int, month_int, day_int))
                end_date = timezone.make_aware(
                    datetime(year_int, month_int, day_int, 23, 59, 59)
                )
                queryset = queryset.filter(time__gte=start_date, time__lte=end_date)
            except (ValueError, TypeError):
                pass

        # Filter for "Unknown" (photos without time)
        if year == "Unknown":
            queryset = queryset.filter(Q(time__isnull=True) | Q(time=""))

        return queryset

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

    def get_queryset(self):
        """Filter queryset based on query parameters."""
        queryset = super().get_queryset()

        # Filter by path prefix
        path_prefix = self.request.query_params.get("path_prefix", None)
        if path_prefix:
            # Normalize path separators
            normalized_prefix = path_prefix.replace("\\", "/")
            queryset = queryset.filter(path__startswith=normalized_prefix)

        return queryset

    def get_serializer_context(self):
        """Add request to serializer context for image URLs."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
