"""Serializers for the album app."""

from rest_framework import serializers
from .models import Album


class AlbumSerializer(serializers.ModelSerializer):
    """Serializer for Album model."""

    photos_count = serializers.SerializerMethodField()

    class Meta:
        model = Album
        fields = [
            "id",
            "name",
            "description",
            "photos_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_photos_count(self, obj):
        """Get the count of photos in this album."""
        return obj.photos.count()
