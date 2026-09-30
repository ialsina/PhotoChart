from django.test import TestCase

from .models import OrganizerConfiguration, OrganizerJob, OrganizerOperation
from .serializers import OrganizerConfigurationSerializer
from .services import _core_config


class OrganizerModelTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/organizer-health/")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_job_keeps_operation_audit(self):
        configuration = OrganizerConfiguration.objects.create(
            name="local",
            source="/PhotoUpload",
            destination="/Photos",
        )
        job = OrganizerJob.objects.create(configuration=configuration)
        OrganizerOperation.objects.create(
            job=job,
            status="dry_run",
            source="/PhotoUpload/photo.jpg",
            destination="/Photos/2026/photo.jpg",
        )

        assert job.operations.count() == 1

    def test_serializer_rejects_plaintext_secrets(self):
        serializer = OrganizerConfigurationSerializer(
            data={
                "name": "remote",
                "adapter": "webdav",
                "source": "/in",
                "destination": "/out",
                "adapter_options": {"password": "secret"},
            }
        )

        assert not serializer.is_valid()
        assert "adapter_options" in serializer.errors

    def test_full_configuration_maps_to_core(self):
        configuration = OrganizerConfiguration.objects.create(
            name="configured",
            source="/in",
            destination="/out",
            timezone="Europe/Berlin",
            collision="fail",
            scan_interval_seconds=15,
            day_starts_at=4,
            stability={"interval_seconds": 2, "checks": 3},
            retry={"attempts": 2, "initial_seconds": 1, "multiplier": 2},
        )
        job = OrganizerJob.objects.create(configuration=configuration)

        config = _core_config(job)

        assert config.timezone == "Europe/Berlin"
        assert config.collision == "fail"
        assert config.scan_interval_seconds == 15
        assert config.day_starts_at == 4
        assert config.stability.checks == 3
        assert config.retry.attempts == 2

    def test_serializer_rejects_unsupported_workers(self):
        serializer = OrganizerConfigurationSerializer(
            data={
                "name": "parallel",
                "source": "/in",
                "destination": "/out",
                "workers": 2,
            }
        )

        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_disabled_configuration_cannot_run(self):
        configuration = OrganizerConfiguration.objects.create(
            name="disabled",
            source="/in",
            destination="/out",
            enabled=False,
        )

        response = self.client.post(
            f"/api/organizer-configurations/{configuration.pk}/run/",
            {"dry_run": True},
        )

        assert response.status_code == 409
        assert OrganizerJob.objects.count() == 0
