"""API views for the photograph app."""

import re
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

    queryset = Photograph.objects.all().prefetch_related("paths", "albums")
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

    queryset = (
        PhotoPath.objects.all()
        .select_related("photograph")
        .prefetch_related("photograph__paths", "photograph__albums")
    )
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

    def _extract_segments_from_paths(self, paths, path_prefix=""):
        """Extract directory/file segments from a list of paths.

        Args:
            paths: List of path strings
            path_prefix: Optional prefix to filter and remove from paths

        Returns:
            Dictionary mapping (segment_name, is_directory) to set of paths
        """
        segments = {}  # key: (segment_name, is_directory), value: set of paths

        # Normalize prefix
        normalized_prefix = (
            path_prefix.replace("\\", "/").strip("/") if path_prefix else ""
        )

        for path_obj in paths:
            if not path_obj:
                continue

            # Normalize path separators
            normalized_path = path_obj.replace("\\", "/")
            normalized_path_clean = normalized_path.strip("/")

            # Remove prefix and get remaining path
            if normalized_prefix:
                if normalized_path_clean.startswith(normalized_prefix + "/"):
                    remaining = normalized_path_clean[len(normalized_prefix) + 1 :]
                elif normalized_path_clean == normalized_prefix:
                    continue  # This is the prefix itself, skip
                else:
                    continue
            else:
                remaining = normalized_path_clean

            if not remaining:
                continue

            # Get first segment (directory or file)
            # Split on "/" and get the first non-empty part
            parts = [p for p in remaining.split("/") if p]  # Filter out empty parts
            if len(parts) > 0:
                first_segment = parts[0]
                is_directory = len(parts) > 1  # Has more parts after the first

                # Track this segment
                segment_key = (first_segment, is_directory)
                if segment_key not in segments:
                    segments[segment_key] = set()
                segments[segment_key].add(normalized_path)  # Store path for counting

        return segments

    @action(detail=False, methods=["get"])
    def directories(self, request):
        """Get directory structure for a given path prefix."""
        import logging

        logger = logging.getLogger(__name__)

        try:
            path_prefix = request.query_params.get("path_prefix", "")
            normalized_prefix = path_prefix.replace("\\", "/") if path_prefix else ""

            # Build queryset - only get paths we need
            if normalized_prefix:
                # Normalize prefix for database query
                normalized_prefix_clean = normalized_prefix.strip("/")
                # Try multiple patterns to match paths with/without leading slashes
                from django.db.models import Q

                # Pattern 1: prefix/ (e.g., "home/")
                pattern1 = normalized_prefix_clean + "/"
                # Pattern 2: /prefix/ (e.g., "/home/")
                pattern2 = "/" + normalized_prefix_clean + "/"
                # Pattern 3: prefix exactly (for files, e.g., "home")
                pattern3 = normalized_prefix_clean

                queryset = PhotoPath.objects.filter(
                    Q(path__startswith=pattern1)
                    | Q(path__startswith=pattern2)
                    | Q(path=pattern3)
                )
            else:
                # Root level - get all paths
                queryset = PhotoPath.objects.all()

            # Get distinct paths and process them in Python
            # Limit to prevent memory issues with very large datasets
            paths = list(queryset.values_list("path", flat=True).distinct()[:10000])

            logger.debug(f"Found {len(paths)} paths for prefix: {normalized_prefix}")

            # Extract segments using helper function
            segments = self._extract_segments_from_paths(paths, normalized_prefix)

            # Build result with counts
            directories = {}
            files = {}

            for (segment_name, is_directory), path_set in segments.items():
                count = len(path_set)
                if is_directory:
                    directories[segment_name] = count
                else:
                    files[segment_name] = count

            # Combine and sort results
            result = [
                {"name": name, "is_directory": True, "count": count}
                for name, count in sorted(directories.items())
            ] + [
                {"name": name, "is_directory": False, "count": count}
                for name, count in sorted(files.items())
            ]

            logger.debug(
                f"Returning {len(result)} segments: {len(directories)} directories, {len(files)} files"
            )
            if result:
                logger.debug(f"Sample segments: {result[:5]}")
            return Response(result)
        except Exception as e:
            logger.error(f"Error in directories endpoint: {str(e)}", exc_info=True)
            return Response([])

    def get_serializer_context(self):
        """Add request to serializer context for image URLs."""
        context = super().get_serializer_context()
        context["request"] = self.request
        return context
