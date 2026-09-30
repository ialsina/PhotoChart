"""Serializers for the planner app."""

from rest_framework import serializers
from .models import PlannedAction


class PlannedActionSerializer(serializers.ModelSerializer):
    """Serializer for PlannedAction model."""

    def validate(self, attrs):
        action_type = attrs.get(
            "action_type", getattr(self.instance, "action_type", None)
        )
        photograph = attrs.get("photograph", getattr(self.instance, "photograph", None))
        job = attrs.get("organizer_job", getattr(self.instance, "organizer_job", None))
        configuration = attrs.get(
            "organizer_configuration",
            getattr(self.instance, "organizer_configuration", None),
        )
        if action_type == PlannedAction.ActionType.DELETE and not photograph:
            raise serializers.ValidationError("DELETE actions require a photograph.")
        if action_type == PlannedAction.ActionType.ORGANIZE and (
            not photograph or not configuration
        ):
            raise serializers.ValidationError(
                "ORGANIZE actions require a photograph and configuration."
            )
        if action_type == PlannedAction.ActionType.RETRY and not job:
            raise serializers.ValidationError("RETRY actions require an organizer job.")
        return attrs

    class Meta:
        model = PlannedAction
        fields = "__all__"
        read_only_fields = [
            "id",
            "status",
            "task_id",
            "error",
            "started_at",
            "finished_at",
            "created_at",
            "updated_at",
        ]
