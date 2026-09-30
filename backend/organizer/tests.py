import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth.models import Permission, User
from django.test import Client
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import (
    DuplicateGroup,
    DuplicateScan,
    OrganizerConfiguration,
    OrganizerJob,
    OrganizerOperation,
)
from .serializers import OrganizerConfigurationSerializer
from .services import _core_config
from .tasks import acquire_lease, recover_stale_jobs, scan_duplicates


class OrganizerModelTests(TestCase):
    def test_health_endpoint(self):
        response = self.client.get("/api/organizer-health/")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_request_id_is_returned(self):
        response = self.client.get("/livez", HTTP_X_REQUEST_ID="test-request-123")

        assert response["X-Request-ID"] == "test-request-123"

    @patch("backend.health.redis.Redis.from_url")
    def test_readiness_checks_database_redis_and_worker(self, from_url):
        client = Mock()
        client.get.return_value = str(timezone.now().timestamp()).encode()
        from_url.return_value = client

        response = self.client.get("/readyz")

        assert response.status_code == 200
        assert response.json()["worker"] == "available"

    @override_settings(METRICS_TOKEN="metrics-secret")
    def test_metrics_require_bearer_token(self):
        assert self.client.get("/metrics").status_code == 403

        response = self.client.get(
            "/metrics", HTTP_AUTHORIZATION="Bearer metrics-secret"
        )

        assert response.status_code == 200
        assert b"photochart_organizer_jobs" in response.content

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
        user = User.objects.create_user("operator", password="secret")
        user.user_permissions.add(Permission.objects.get(codename="operate_organizer"))
        self.client.login(username="operator", password="secret")

        response = self.client.post(
            f"/api/organizer-configurations/{configuration.pk}/run/",
            {"dry_run": True},
        )

        assert response.status_code == 409
        assert OrganizerJob.objects.count() == 0

    def test_api_requires_authentication(self):
        response = self.client.get("/api/organizer-configurations/")

        assert response.status_code in {401, 403}

    def test_session_login_requires_csrf_and_returns_operator_role(self):
        user = User.objects.create_user("operator", password="secret")
        user.user_permissions.add(Permission.objects.get(codename="operate_organizer"))
        client = Client(enforce_csrf_checks=True)
        client.get("/api/session/")

        rejected = client.post(
            "/api/session/login/",
            data=json.dumps({"username": "operator", "password": "secret"}),
            content_type="application/json",
        )
        accepted = client.post(
            "/api/session/login/",
            data=json.dumps({"username": "operator", "password": "secret"}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value,
        )

        assert rejected.status_code == 403
        assert accepted.status_code == 200
        assert accepted.json()["operator"] is True

    def test_run_is_enqueued_and_returns_immediately(self):
        configuration = OrganizerConfiguration.objects.create(
            name="queued",
            source="/in",
            destination="/out",
        )
        user = User.objects.create_user("operator", password="secret")
        user.user_permissions.add(Permission.objects.get(codename="operate_organizer"))
        self.client.login(username="operator", password="secret")

        with patch("organizer.views.execute_job_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    f"/api/organizer-configurations/{configuration.pk}/run/",
                    {"dry_run": True},
                )

        assert response.status_code == 202
        job = OrganizerJob.objects.get()
        assert job.status == OrganizerJob.Status.PENDING
        delay.assert_called_once_with(job.pk)

    def test_configuration_lease_prevents_overlapping_jobs(self):
        configuration = OrganizerConfiguration.objects.create(
            name="leased",
            source="/in",
            destination="/out",
        )
        first = OrganizerJob.objects.create(configuration=configuration)
        second = OrganizerJob.objects.create(configuration=configuration)

        assert acquire_lease(first) is True
        assert acquire_lease(second) is False

    def test_stale_job_recovery_marks_job_failed(self):
        configuration = OrganizerConfiguration.objects.create(
            name="stale",
            source="/in",
            destination="/out",
        )
        job = OrganizerJob.objects.create(
            configuration=configuration,
            status=OrganizerJob.Status.RUNNING,
            heartbeat_at=timezone.now() - timedelta(hours=1),
        )
        acquire_lease(job)

        recovered = recover_stale_jobs()

        job.refresh_from_db()
        assert recovered == 1
        assert job.status == OrganizerJob.Status.FAILED
        assert job.configuration.lease.owner_job is None

    def test_job_summaries_and_operation_filters_are_bounded(self):
        configuration = OrganizerConfiguration.objects.create(
            name="filtered",
            source="/in",
            destination="/out",
        )
        job = OrganizerJob.objects.create(configuration=configuration)
        other_job = OrganizerJob.objects.create(configuration=configuration)
        OrganizerOperation.objects.create(
            job=job,
            status="failed",
            source="/in/failed.jpg",
        )
        OrganizerOperation.objects.create(
            job=other_job,
            status="copied",
            source="/in/copied.jpg",
        )
        user = User.objects.create_user("reader", password="secret")
        self.client.login(username="reader", password="secret")

        jobs = self.client.get("/api/organizer-jobs/").json()["results"]
        operations = self.client.get(
            f"/api/organizer-operations/?job={job.pk}&status=failed"
        ).json()["results"]

        assert "operations" not in jobs[0]
        assert {operation["source"] for operation in operations} == {"/in/failed.jpg"}

    def test_duplicate_scan_populates_persistent_groups(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.jpg").write_bytes(b"same")
            (root / "two.jpg").write_bytes(b"same")
            configuration = OrganizerConfiguration.objects.create(
                name="duplicates",
                source=str(root),
                destination=str(root / "organized"),
            )
            scan = DuplicateScan.objects.create(configuration=configuration)

            status = scan_duplicates(scan.pk)

        scan.refresh_from_db()
        group = DuplicateGroup.objects.get(configuration=configuration)
        assert status == DuplicateScan.Status.COMPLETED
        assert scan.status == DuplicateScan.Status.COMPLETED
        assert len(group.paths) == 2
        assert group.scan == scan
