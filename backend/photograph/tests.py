"""Django tests for IngestJob model, API, and Celery task."""

from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.utils import timezone

from .models import IngestJob


def _make_operator(username: str = "operator", password: str = "secret") -> User:
    user = User.objects.create_user(username, password=password)
    user.user_permissions.add(Permission.objects.get(codename="operate_organizer"))
    return user


def _make_reader(username: str = "reader", password: str = "secret") -> User:
    return User.objects.create_user(username, password=password)


# ---------------------------------------------------------------------------
# Model smoke test
# ---------------------------------------------------------------------------


class IngestJobModelTest(TestCase):
    def test_str_representation(self) -> None:
        job = IngestJob(path="/photos/Photos", status=IngestJob.Status.PENDING)
        assert "/photos/Photos" in str(job)
        assert "PENDING" in str(job)

    def test_defaults(self) -> None:
        job = IngestJob.objects.create(path="/photos/Photos")
        assert job.status == IngestJob.Status.PENDING
        assert job.recursive is True
        assert job.calculate_checksum is True
        assert job.store_images is True
        assert job.count == 0
        assert job.error == ""


# ---------------------------------------------------------------------------
# API – permissions
# ---------------------------------------------------------------------------


class IngestJobApiPermissionTest(TestCase):
    def test_list_requires_authentication(self) -> None:
        response = self.client.get("/api/ingest-jobs/")
        assert response.status_code in {401, 403}

    def test_create_requires_operator(self) -> None:
        reader = _make_reader()
        self.client.login(username="reader", password="secret")
        response = self.client.post(
            "/api/ingest-jobs/",
            {"path": "/photos/Photos"},
            content_type="application/json",
        )
        assert response.status_code in {401, 403}

    def test_create_as_operator_queues_task(self) -> None:
        _make_operator()
        self.client.login(username="operator", password="secret")

        with patch("photograph.tasks.run_ingest_job.delay") as mock_delay:
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(
                    "/api/ingest-jobs/",
                    {"path": "/photos/Photos"},
                    content_type="application/json",
                )

        assert response.status_code == 202
        job = IngestJob.objects.get()
        assert job.status == IngestJob.Status.PENDING
        assert job.path == "/photos/Photos"
        mock_delay.assert_called_once_with(job.pk)

    def test_read_as_authenticated_non_operator(self) -> None:
        IngestJob.objects.create(path="/photos/Photos")
        _make_reader()
        self.client.login(username="reader", password="secret")

        response = self.client.get("/api/ingest-jobs/")
        assert response.status_code == 200

    def test_create_records_requested_by(self) -> None:
        op = _make_operator()
        self.client.login(username="operator", password="secret")

        with patch("photograph.tasks.run_ingest_job.delay"):
            with self.captureOnCommitCallbacks(execute=True):
                self.client.post(
                    "/api/ingest-jobs/",
                    {"path": "/photos/Photos"},
                    content_type="application/json",
                )

        job = IngestJob.objects.get()
        assert job.requested_by == op


# ---------------------------------------------------------------------------
# API – validation
# ---------------------------------------------------------------------------


class IngestJobApiValidationTest(TestCase):
    def setUp(self) -> None:
        _make_operator()
        self.client.login(username="operator", password="secret")

    def test_empty_path_rejected(self) -> None:
        response = self.client.post(
            "/api/ingest-jobs/",
            {"path": ""},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_proc_path_rejected(self) -> None:
        response = self.client.post(
            "/api/ingest-jobs/",
            {"path": "/proc/1/environ"},
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_traversal_path_rejected(self) -> None:
        response = self.client.post(
            "/api/ingest-jobs/",
            {"path": "/mnt/../etc/passwd"},
            content_type="application/json",
        )
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


class IngestJobTaskTest(TestCase):
    def test_task_marks_completed_on_success(self) -> None:
        job = IngestJob.objects.create(path="/photos/Photos")
        mock_result = {
            "success": True,
            "count": 7,
            "checksums_calculated": 7,
            "images_stored": 7,
            "errors": [],
        }
        with patch(
            "photochart.ingest_runner.choose_and_run_ingest",
            return_value=mock_result,
        ):
            from .tasks import run_ingest_job

            status = run_ingest_job(job.pk)

        job.refresh_from_db()
        assert status == IngestJob.Status.COMPLETED
        assert job.status == IngestJob.Status.COMPLETED
        assert job.count == 7
        assert job.checksums_calculated == 7
        assert job.images_stored == 7
        assert job.error == ""
        assert job.started_at is not None
        assert job.finished_at is not None

    def test_task_marks_failed_when_ingest_returns_failure(self) -> None:
        job = IngestJob.objects.create(path="/nonexistent")
        mock_result = {
            "success": False,
            "count": 0,
            "checksums_calculated": 0,
            "images_stored": 0,
            "errors": ["Path does not exist"],
        }
        with patch(
            "photochart.ingest_runner.choose_and_run_ingest",
            return_value=mock_result,
        ):
            from .tasks import run_ingest_job

            status = run_ingest_job(job.pk)

        job.refresh_from_db()
        assert status == IngestJob.Status.FAILED
        assert "Path does not exist" in job.error

    def test_task_marks_failed_on_exception(self) -> None:
        job = IngestJob.objects.create(path="/photos/Photos")
        with patch(
            "photochart.ingest_runner.choose_and_run_ingest",
            side_effect=RuntimeError("unexpected"),
        ):
            from .tasks import run_ingest_job

            status = run_ingest_job(job.pk)

        job.refresh_from_db()
        assert status == IngestJob.Status.FAILED
        assert "unexpected" in job.error

    def test_task_passes_job_options_to_runner(self) -> None:
        job = IngestJob.objects.create(
            path="/photos/Photos",
            device="MyDisk (/mnt/camera)",
            recursive=False,
            calculate_checksum=False,
            store_images=False,
        )
        with patch(
            "photochart.ingest_runner.choose_and_run_ingest",
            return_value={
                "success": True,
                "count": 0,
                "checksums_calculated": 0,
                "images_stored": 0,
                "errors": [],
            },
        ) as mock_runner:
            from .tasks import run_ingest_job

            run_ingest_job(job.pk)

        call_kwargs = mock_runner.call_args.kwargs
        assert call_kwargs["device"] == "MyDisk (/mnt/camera)"
        assert call_kwargs["recursive"] is False
        assert call_kwargs["calculate_checksum"] is False
        assert call_kwargs["store_images"] is False
