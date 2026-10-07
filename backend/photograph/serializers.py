"""Serializers for the photograph app."""

from rest_framework import serializers
from .models import Photograph, PhotoPath, IngestJob


class PhotoPathSerializer(serializers.ModelSerializer):
    """Serializer for PhotoPath model."""

    photograph_image_url = serializers.SerializerMethodField()
    photograph_paths_count = serializers.SerializerMethodField()
    other_paths = serializers.SerializerMethodField()
    photograph_has_errors = serializers.SerializerMethodField()
    photograph_model = serializers.SerializerMethodField()
    photograph_albums = serializers.SerializerMethodField()

    class Meta:
        model = PhotoPath
        fields = [
            "id",
            "path",
            "device",
            "photograph",
            "size",
            "photograph_image_url",
            "photograph_paths_count",
            "photograph_has_errors",
            "photograph_model",
            "photograph_albums",
            "other_paths",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_photograph_image_url(self, obj):
        """Get the image URL for the linked photograph if it exists."""
        if obj.photograph and obj.photograph.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.photograph.thumbnail.url)
            return obj.photograph.thumbnail.url
        return None

    def get_photograph_paths_count(self, obj):
        """Get the total number of paths linked to this photograph."""
        if obj.photograph:
            # Use prefetched paths if available to avoid extra query
            # When prefetched, we can use len() which is O(1) for prefetched querysets
            if (
                hasattr(obj.photograph, "_prefetched_objects_cache")
                and "paths" in obj.photograph._prefetched_objects_cache
            ):
                return len(obj.photograph._prefetched_objects_cache["paths"])
            # Fallback to count() if not prefetched
            return obj.photograph.paths.count()
        return 0

    def get_other_paths(self, obj):
        """Get other paths that link to the same photograph (excluding this one)."""
        if obj.photograph:
            # Use prefetched paths if available to avoid extra query
            if (
                hasattr(obj.photograph, "_prefetched_objects_cache")
                and "paths" in obj.photograph._prefetched_objects_cache
            ):
                # Use prefetched queryset - filter in Python
                other_paths = [
                    p
                    for p in obj.photograph._prefetched_objects_cache["paths"]
                    if p.id != obj.id
                ]
            else:
                # Fallback to database query
                other_paths = obj.photograph.paths.exclude(id=obj.id)
            return [
                {
                    "id": path.id,
                    "path": path.path,
                    "device": path.device,
                }
                for path in other_paths[:10]  # Limit to 10 for performance
            ]
        return []

    def get_photograph_has_errors(self, obj):
        """Get has_errors from the linked photograph if it exists."""
        if obj.photograph:
            return obj.photograph.has_errors
        return None

    def get_photograph_model(self, obj):
        """Get model from the linked photograph if it exists."""
        if obj.photograph:
            return obj.photograph.model
        return None

    def get_photograph_albums(self, obj):
        """Get albums from the linked photograph if it exists."""
        if obj.photograph:
            # Use prefetched albums if available
            if (
                hasattr(obj.photograph, "_prefetched_objects_cache")
                and "albums" in obj.photograph._prefetched_objects_cache
            ):
                albums = obj.photograph._prefetched_objects_cache["albums"]
            else:
                albums = obj.photograph.albums.all()
            return [
                {
                    "id": album.id,
                    "name": album.name,
                }
                for album in albums
            ]
        return []


class PhotographSerializer(serializers.ModelSerializer):
    """Serializer for Photograph model."""

    paths = PhotoPathSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()
    albums = serializers.SerializerMethodField()

    class Meta:
        model = Photograph
        fields = [
            "id",
            "checksum",
            "thumbnail",
            "image_url",
            "time",
            "model",
            "has_errors",
            "paths",
            "albums",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_image_url(self, obj):
        """Get the URL for the image if it exists."""
        if obj.thumbnail and hasattr(obj.thumbnail, "url"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None

    def get_albums(self, obj):
        """Get list of albums this photograph belongs to."""
        # Use prefetched albums if available
        if (
            hasattr(obj, "_prefetched_objects_cache")
            and "albums" in obj._prefetched_objects_cache
        ):
            albums = obj._prefetched_objects_cache["albums"]
        else:
            albums = obj.albums.all()
        return [
            {
                "id": album.id,
                "name": album.name,
            }
            for album in albums
        ]


class IngestJobSerializer(serializers.ModelSerializer):
    """Serializer for IngestJob – create and read ingest jobs."""

    requested_by_username = serializers.SerializerMethodField()

    class Meta:
        model = IngestJob
        fields = [
            "id",
            "path",
            "mount_root",
            "device",
            "recursive",
            "calculate_checksum",
            "store_images",
            "resolution",
            "retry_thumbnails",
            "raw_only",
            "status",
            "task_id",
            "error",
            "count",
            "checksums_calculated",
            "images_stored",
            "started_at",
            "finished_at",
            "created_at",
            "requested_by",
            "requested_by_username",
        ]
        read_only_fields = [
            "id",
            "status",
            "task_id",
            "error",
            "count",
            "checksums_calculated",
            "images_stored",
            "started_at",
            "finished_at",
            "created_at",
            "requested_by",
            "requested_by_username",
        ]

    def get_requested_by_username(self, obj):
        if obj.requested_by:
            return obj.requested_by.username
        return None

    def validate_path(self, value: str) -> str:
        """Reject obviously dangerous or empty paths early (full validation is
        deferred to ``choose_and_run_ingest`` at task-execution time so that
        settings-based prefix rules are applied consistently)."""
        from photochart.ingest.runner import validate_ingest_path

        try:
            return validate_ingest_path(value, allowed_prefixes=None)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
