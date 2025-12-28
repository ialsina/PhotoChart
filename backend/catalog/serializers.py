"""Serializers for the catalog app."""

from rest_framework import serializers
from .models import Hash, Directory, DirKind, Location, TimeLoc


class DirKindSerializer(serializers.ModelSerializer):
    """Serializer for DirKind model."""

    class Meta:
        model = DirKind
        fields = ["id", "name"]


class LocationSerializer(serializers.ModelSerializer):
    """Serializer for Location model."""

    class Meta:
        model = Location
        fields = ["id", "name"]


class DirectorySerializer(serializers.ModelSerializer):
    """Serializer for Directory model."""

    kind_name = serializers.CharField(source="kind.name", read_only=True)

    class Meta:
        model = Directory
        fields = [
            "id",
            "path",
            "last_modified",
            "mirror",
            "kind",
            "kind_name",
        ]


class HashSerializer(serializers.ModelSerializer):
    """Serializer for Hash model."""

    class Meta:
        model = Hash
        fields = ["id", "path", "hash"]


class TimeLocSerializer(serializers.ModelSerializer):
    """Serializer for TimeLoc model."""

    directory_path = serializers.CharField(source="path.path", read_only=True)
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = TimeLoc
        fields = [
            "id",
            "path",
            "directory_path",
            "timestamp",
            "location",
            "location_name",
        ]
