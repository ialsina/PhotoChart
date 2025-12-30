"""Serializers for the planner app."""

from rest_framework import serializers
from .models import PlannedAction


class PlannedActionSerializer(serializers.ModelSerializer):
    """Serializer for PlannedAction model."""

    class Meta:
        model = PlannedAction
        fields = [
            "id",
            "action_type",
            "photograph",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
