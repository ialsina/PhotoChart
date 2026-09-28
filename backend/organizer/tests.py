from django.test import TestCase

from .models import OrganizerConfiguration, OrganizerJob, OrganizerOperation
from .serializers import OrganizerConfigurationSerializer


class OrganizerModelTests(TestCase):
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
