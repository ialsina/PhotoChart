"""Serializers for the photograph app."""

from rest_framework import serializers
from .models import Photograph, PhotoPath


class PhotoPathSerializer(serializers.ModelSerializer):
    """Serializer for PhotoPath model."""

    class Meta:
        model = PhotoPath
        fields = ["id", "path", "device", "photograph", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


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
