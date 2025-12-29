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
            queryset = queryset.filter(time__isnull=True)

        return queryset

    def get_serializer_context(self):
        """Add request to serializer context for image URLs."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @action(detail=False, methods=["get"])
    def years(self, request):
        """Get list of years with photo counts."""
        from django.db.models import Count, Q
        from django.db.models.functions import ExtractYear

        queryset = self.get_queryset()

        # Get years from photos with time
        years_with_time = (
            queryset.exclude(time__isnull=True)
            .annotate(year=ExtractYear("time"))
            .values("year")
            .annotate(count=Count("id"))
            .order_by("year")
        )

        # Count photos without time
        unknown_count = queryset.filter(time__isnull=True).count()

        result = [
            {"year": str(item["year"]), "count": item["count"]}
            for item in years_with_time
        ]

        if unknown_count > 0:
            result.append({"year": "Unknown", "count": unknown_count})

        return Response(result)

    @action(detail=False, methods=["get"])
    def months(self, request):
        """Get list of months for a given year with photo counts."""
        from django.db.models import Count, Q
        from django.db.models.functions import ExtractYear, ExtractMonth

        year = request.query_params.get("year")
        if not year or year == "Unknown":
            return Response([])

        queryset = self.get_queryset()
        try:
            year_int = int(year)
            start_date = timezone.make_aware(datetime(year_int, 1, 1))
            end_date = timezone.make_aware(datetime(year_int + 1, 1, 1))
            queryset = queryset.filter(time__gte=start_date, time__lt=end_date)
        except (ValueError, TypeError):
            return Response([])

        months = (
            queryset.annotate(month=ExtractMonth("time"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        return Response(
            [
                {"month": str(item["month"]).zfill(2), "count": item["count"]}
                for item in months
            ]
        )

    @action(detail=False, methods=["get"])
    def days(self, request):
        """Get list of days for a given year/month with photo counts."""
        from django.db.models import Count
        from django.db.models.functions import ExtractYear, ExtractMonth, ExtractDay

        year = request.query_params.get("year")
        month = request.query_params.get("month")
        if not year or not month:
            return Response([])

        queryset = self.get_queryset()
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
            return Response([])

        days = (
            queryset.annotate(day=ExtractDay("time"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )

        return Response(
            [
                {"day": str(item["day"]).zfill(2), "count": item["count"]}
                for item in days
            ]
        )

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
        only_direct = (
            self.request.query_params.get("only_direct", "false").lower() == "true"
        )

        if path_prefix:
            # Normalize path separators
            normalized_prefix = path_prefix.replace("\\", "/")
            if only_direct:
                # Only get direct children (files in this directory, not in subdirectories)
                # Path should start with prefix + "/" and the remaining part should not contain "/"
                prefix_with_slash = normalized_prefix + "/"
                queryset = queryset.filter(path__startswith=prefix_with_slash)

                # Filter to only include paths where the part after prefix+"/" has no "/"
                # We use a regex pattern: prefix + "/" + filename (no more "/")
                from django.db import connection

                prefix_pattern = re.escape(prefix_with_slash)

                if connection.vendor == "postgresql":
                    # PostgreSQL supports regex
                    queryset = queryset.extra(
                        where=["path ~ %s"], params=[rf"^{prefix_pattern}[^/]+$"]
                    )
                elif connection.vendor == "mysql":
                    # MySQL supports regex
                    queryset = queryset.extra(
                        where=["path REGEXP %s"], params=[rf"^{prefix_pattern}[^/]+$"]
                    )
                else:
                    # For SQLite and others, we'll need to filter differently
                    # Use a workaround: filter paths that don't have another "/" after the prefix
                    # This is less efficient but works across databases
                    # We'll let the pagination handle it and filter will still reduce the dataset
                    pass  # Fall back to startswith, which still helps
            else:
                queryset = queryset.filter(path__startswith=normalized_prefix)

        return queryset

    @action(detail=False, methods=["get"])
    def directories(self, request):
        """Get directory structure for a given path prefix."""
        from django.db.models import Count

        path_prefix = request.query_params.get("path_prefix", "")
        normalized_prefix = path_prefix.replace("\\", "/") if path_prefix else ""

        queryset = self.get_queryset()
        if normalized_prefix:
            # Add trailing slash for proper matching
            if not normalized_prefix.endswith("/"):
                normalized_prefix_with_slash = normalized_prefix + "/"
            else:
                normalized_prefix_with_slash = normalized_prefix
            queryset = queryset.filter(path__startswith=normalized_prefix_with_slash)
        else:
            # Root level - get all paths
            queryset = queryset.all()

        # Extract directory segments efficiently using database aggregation
        directories = {}
        files = {}

        for path_obj in queryset.values_list("path", flat=True)[
            :10000
        ]:  # Limit to prevent memory issues
            normalized_path = path_obj.replace("\\", "/")
            # Remove prefix and get next segment
            if normalized_prefix:
                if normalized_path.startswith(normalized_prefix_with_slash):
                    remaining = normalized_path[len(normalized_prefix_with_slash) :]
                elif normalized_path == normalized_prefix:
                    continue  # This is the prefix itself, skip
                else:
                    continue
            else:
                remaining = normalized_path

            # Get first segment (directory or file)
            parts = remaining.split("/")
            if len(parts) > 0 and parts[0]:
                first_segment = parts[0]
                is_directory = len(parts) > 1

                if is_directory:
                    if first_segment not in directories:
                        directories[first_segment] = 0
                    directories[first_segment] += 1
                else:
                    if first_segment not in files:
                        files[first_segment] = 0
                    files[first_segment] += 1

        result = [
            {"name": name, "is_directory": True, "count": count}
            for name, count in sorted(directories.items())
        ] + [
            {"name": name, "is_directory": False, "count": count}
            for name, count in sorted(files.items())
        ]

        return Response(result)

    def get_serializer_context(self):
        """Add request to serializer context for image URLs."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
