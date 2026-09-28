from rest_framework import serializers

from .models import (
    DuplicateGroup,
    OrganizerConfiguration,
    OrganizerJob,
    OrganizerOperation,
)


class OrganizerConfigurationSerializer(serializers.ModelSerializer):
    def validate_adapter_options(self, value):
        forbidden = {"password", "access_token", "secret_access_key"}
        exposed = forbidden.intersection(value)
        if exposed:
            raise serializers.ValidationError(
                "Store secrets in environment variables and provide *_env options: "
                + ", ".join(sorted(exposed))
            )
        return value

    class Meta:
        model = OrganizerConfiguration
        fields = "__all__"


class OrganizerOperationSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrganizerOperation
        fields = "__all__"
        read_only_fields = [
            "id",
            "job",
            "status",
            "source",
            "destination",
            "object_id",
            "capture_date",
            "date_source",
            "detail",
            "verified",
            "created_at",
        ]


class OrganizerJobSerializer(serializers.ModelSerializer):
    operations = OrganizerOperationSerializer(many=True, read_only=True)

    class Meta:
        model = OrganizerJob
        fields = "__all__"
        read_only_fields = [
            "status",
            "error",
            "started_at",
            "finished_at",
            "created_at",
        ]


class DuplicateGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = DuplicateGroup
        fields = "__all__"
        read_only_fields = [
            "id",
            "checksum",
            "size",
            "paths",
            "wasted_bytes",
            "scanned_at",
        ]
