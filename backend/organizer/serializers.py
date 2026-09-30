from rest_framework import serializers

from photochart.organizer.config import (
    OrganizerConfig,
    RetryConfig,
    StabilityConfig,
)

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

    def validate(self, attrs):
        current = self.instance

        def value(name, default=None):
            if name in attrs:
                return attrs[name]
            if current is not None:
                return getattr(current, name)
            return default

        try:
            OrganizerConfig(
                source=value("source", ""),
                destination=value("destination", ""),
                adapter=value("adapter", "local"),
                adapter_options=value("adapter_options", {}),
                pattern=value("pattern", "%Y/%YQ%Q/%Y%M%D"),
                quarantine=value("quarantine"),
                mode=value("mode", "move"),
                timezone=value("timezone", "UTC"),
                collision=value("collision", "suffix"),
                duplicate_detection=value("duplicate_detection", "size_then_hash"),
                workers=value("workers", 1),
                scan_interval_seconds=value("scan_interval_seconds", 60),
                process_after=value("process_after"),
                include_first=value("include_first", True),
                day_starts_at=value("day_starts_at", 0),
                media_extensions=tuple(value("media_extensions", [])),
                date_priority=tuple(value("date_priority", [])),
                stability=StabilityConfig(**value("stability", {})),
                retry=RetryConfig(**value("retry", {})),
            )
        except (TypeError, ValueError) as error:
            raise serializers.ValidationError(str(error)) from error
        return attrs

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
    operation_count = serializers.IntegerField(read_only=True)

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


class OrganizerJobSummarySerializer(serializers.ModelSerializer):
    operation_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = OrganizerJob
        fields = "__all__"


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
