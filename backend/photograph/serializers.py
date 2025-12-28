"""Serializers for the photograph app."""

from rest_framework import serializers
from .models import Photograph, PhotoPath


class PhotoPathSerializer(serializers.ModelSerializer):
    """Serializer for PhotoPath model."""

    photograph_image_url = serializers.SerializerMethodField()
    photograph_paths_count = serializers.SerializerMethodField()
    other_paths = serializers.SerializerMethodField()

    class Meta:
        model = PhotoPath
        fields = [
            "id",
            "path",
            "device",
            "photograph",
            "photograph_image_url",
            "photograph_paths_count",
            "other_paths",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_photograph_image_url(self, obj):
        """Get the image URL for the linked photograph if it exists."""
        if obj.photograph and obj.photograph.image:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.photograph.image.url)
            return obj.photograph.image.url
        return None

    def get_photograph_paths_count(self, obj):
        """Get the total number of paths linked to this photograph."""
        if obj.photograph:
            return obj.photograph.paths.count()
        return 0

    def get_other_paths(self, obj):
        """Get other paths that link to the same photograph (excluding this one)."""
        if obj.photograph:
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


class PhotographSerializer(serializers.ModelSerializer):
    """Serializer for Photograph model."""

    paths = PhotoPathSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Photograph
        fields = [
            "id",
            "hash",
            "image",
            "image_url",
            "time",
            "paths",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_image_url(self, obj):
        """Get the URL for the image if it exists."""
        if obj.image and hasattr(obj.image, "url"):
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None
