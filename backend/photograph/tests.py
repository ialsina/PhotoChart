"""Django tests for IngestJob model, API, and Celery task."""

import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Permission, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from .models import IngestJob, PhotoPath, Photograph


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
        assert job.retry_thumbnails is False
        assert job.fix_errors is False
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
            "photochart.ingest.runner.choose_and_run_ingest",
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
            "photochart.ingest.runner.choose_and_run_ingest",
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
            "photochart.ingest.runner.choose_and_run_ingest",
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
            "photochart.ingest.runner.choose_and_run_ingest",
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
        assert call_kwargs["retry_thumbnails"] is False
        assert call_kwargs["fix_errors"] is False
        assert call_kwargs["raw_only"] is False

    def test_task_passes_raw_only_to_runner(self) -> None:
        job = IngestJob.objects.create(path="/photos/Photos", raw_only=True)
        with patch(
            "photochart.ingest.runner.choose_and_run_ingest",
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

        assert mock_runner.call_args.kwargs["raw_only"] is True

    def test_task_passes_retry_thumbnails_to_runner(self) -> None:
        job = IngestJob.objects.create(
            path="/photos/Photos",
            retry_thumbnails=True,
            store_images=False,
        )
        with patch(
            "photochart.ingest.runner.choose_and_run_ingest",
            return_value={
                "success": True,
                "count": 0,
                "checksums_calculated": 0,
                "images_stored": 1,
                "thumbnails_retried": 1,
                "errors": [],
            },
        ) as mock_runner:
            from .tasks import run_ingest_job

            run_ingest_job(job.pk)

        call_kwargs = mock_runner.call_args.kwargs
        assert call_kwargs["retry_thumbnails"] is True

    def test_task_passes_fix_errors_to_runner(self) -> None:
        job = IngestJob.objects.create(
            path="/photos/Photos",
            fix_errors=True,
        )
        with patch(
            "photochart.ingest.runner.choose_and_run_ingest",
            return_value={
                "success": True,
                "count": 0,
                "checksums_calculated": 0,
                "images_stored": 0,
                "errors_repair_attempted": 1,
                "errors_cleared": 1,
                "errors": [],
            },
        ) as mock_runner:
            from .tasks import run_ingest_job

            run_ingest_job(job.pk)

        assert mock_runner.call_args.kwargs["fix_errors"] is True


# ---------------------------------------------------------------------------
# Ingest retry thumbnails
# ---------------------------------------------------------------------------


class IngestRetryThumbnailsTest(TestCase):
    DEVICE = "test-device"

    def _write_minimal_jpeg(self, directory: Path, name: str = "photo.jpg") -> Path:
        # Minimal valid JPEG (1x1)
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
            b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
            b"\x1c $.\x27 ,#\x1c\x1c(7),01444\x1f\x27=9=82<.342\xff\xc0\x00\x0b\x08"
            b"\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01"
            b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06"
            b"\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05"
            b"\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
            b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17'
            b"\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85"
            b"\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5"
            b"\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5"
            b"\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4"
            b"\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5\x7f\xff\xd9"
        )
        path = directory / name
        path.write_bytes(jpeg)
        return path

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_retry_stores_thumbnail_for_existing_path(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    img = self._write_minimal_jpeg(Path(tmp))
                    path_str = str(img.resolve())
                    photograph = Photograph.objects.create()
                    PhotoPath.objects.create(
                        path=path_str, device=self.DEVICE, photograph=photograph
                    )

                    with patch(
                        "photochart.ingest.photos.Photograph.get_image_from_file",
                        return_value=True,
                    ) as mock_get:
                        result = ingest_photos(
                            tmp,
                            device=self.DEVICE,
                            recursive=False,
                            calculate_checksum=False,
                            store_images=True,
                            retry_thumbnails=True,
                        )

                    mock_get.assert_called_once()
                    assert result["count"] == 0
                    assert result["thumbnails_retried"] == 1
                    assert result["images_stored"] == 1
                    assert PhotoPath.objects.count() == 1

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_retry_skips_when_thumbnail_present(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    img = self._write_minimal_jpeg(Path(tmp))
                    path_str = str(img.resolve())
                    photograph = Photograph.objects.create()
                    photograph.thumbnail.save(
                        "existing.jpg",
                        SimpleUploadedFile("existing.jpg", b"thumb"),
                        save=True,
                    )
                    PhotoPath.objects.create(
                        path=path_str, device=self.DEVICE, photograph=photograph
                    )

                    with patch(
                        "photochart.ingest.photos.Photograph.get_image_from_file"
                    ) as mock_get:
                        result = ingest_photos(
                            tmp,
                            device=self.DEVICE,
                            recursive=False,
                            calculate_checksum=False,
                            retry_thumbnails=True,
                        )

                    mock_get.assert_not_called()
                    assert result["thumbnails_retried"] == 0
                    assert result["images_stored"] == 0

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_retry_only_processes_catalogued_missing_thumbnails(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    tmp_path = Path(tmp)
                    catalogued = self._write_minimal_jpeg(tmp_path, "in_db.jpg")
                    self._write_minimal_jpeg(tmp_path, "not_in_db.jpg")
                    photograph = Photograph.objects.create()
                    PhotoPath.objects.create(
                        path=str(catalogued.resolve()),
                        device=self.DEVICE,
                        photograph=photograph,
                    )

                    with patch(
                        "photochart.ingest.photos.Photograph.get_image_from_file",
                        return_value=True,
                    ) as mock_get:
                        result = ingest_photos(
                            tmp,
                            device=self.DEVICE,
                            recursive=False,
                            calculate_checksum=False,
                            retry_thumbnails=True,
                        )

                    mock_get.assert_called_once()
                    assert result["thumbnails_retried"] == 1

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_retry_candidate_collection_uses_batched_db_lookup(self, *_mocks) -> None:
        from photochart.ingest.photos import collect_thumbnail_retry_candidates

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    tmp_path = Path(tmp)
                    paths_on_disk = []
                    for i in range(5):
                        img = self._write_minimal_jpeg(tmp_path, f"p{i}.jpg")
                        paths_on_disk.append(img)
                    photograph = Photograph.objects.create()
                    PhotoPath.objects.create(
                        path=str(paths_on_disk[0].resolve()),
                        device=self.DEVICE,
                        photograph=photograph,
                    )

                    with self.assertNumQueries(2):
                        candidates = collect_thumbnail_retry_candidates(
                            paths_on_disk,
                            self.DEVICE,
                            ingest_path=tmp,
                            mount_table=[],
                        )

                    assert len(candidates) == 1
                    assert candidates[0][0] == paths_on_disk[0]

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_retry_does_not_create_new_paths(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    self._write_minimal_jpeg(Path(tmp))
                    result = ingest_photos(
                        tmp,
                        device=self.DEVICE,
                        recursive=False,
                        calculate_checksum=False,
                        retry_thumbnails=True,
                    )

                    assert PhotoPath.objects.count() == 0
                    assert result["count"] == 0
                    assert result["success"] is True


# ---------------------------------------------------------------------------
# Ingest fix errors
# ---------------------------------------------------------------------------


class IngestFixErrorsTest(TestCase):
    DEVICE = "test-device"

    def _write_minimal_jpeg(self, directory: Path, name: str = "photo.jpg") -> Path:
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
            b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
            b"\x1c $.\x27 ,#\x1c\x1c(7),01444\x1f\x27=9=82<.342\xff\xc0\x00\x0b\x08"
            b"\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01"
            b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06"
            b"\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05"
            b"\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
            b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17'
            b"\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85"
            b"\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5"
            b"\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5"
            b"\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4"
            b"\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5\x7f\xff\xd9"
        )
        path = directory / name
        path.write_bytes(jpeg)
        return path

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_fix_errors_invokes_repair_and_clears_flag(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    img = self._write_minimal_jpeg(Path(tmp))
                    path_str = str(img.resolve())
                    photograph = Photograph.objects.create(has_errors=True)
                    PhotoPath.objects.create(
                        path=path_str, device=self.DEVICE, photograph=photograph
                    )

                    with patch(
                        "photograph.models.Photograph.repair_from_file",
                        return_value=True,
                    ) as mock_repair:
                        result = ingest_photos(
                            tmp,
                            device=self.DEVICE,
                            recursive=False,
                            calculate_checksum=False,
                            store_images=True,
                            fix_errors=True,
                        )

                    mock_repair.assert_called_once()
                    assert result["errors_repair_attempted"] == 1
                    assert result["errors_cleared"] == 1
                    assert PhotoPath.objects.count() == 1

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_fix_errors_skips_when_thumbnail_present(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    img = self._write_minimal_jpeg(Path(tmp))
                    path_str = str(img.resolve())
                    photograph = Photograph.objects.create(has_errors=True)
                    photograph.thumbnail.save(
                        "existing.jpg",
                        SimpleUploadedFile("existing.jpg", b"thumb"),
                        save=True,
                    )
                    PhotoPath.objects.create(
                        path=path_str, device=self.DEVICE, photograph=photograph
                    )

                    with patch(
                        "photograph.models.Photograph.repair_from_file",
                        return_value=True,
                    ) as mock_repair:
                        result = ingest_photos(
                            tmp,
                            device=self.DEVICE,
                            recursive=False,
                            calculate_checksum=False,
                            fix_errors=True,
                            store_images=True,
                        )

                    mock_repair.assert_called_once()
                    call_kwargs = mock_repair.call_args.kwargs
                    assert call_kwargs["store_thumbnail"] is True
                    assert result["errors_repair_attempted"] == 1

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_fix_errors_skips_not_in_catalog(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    self._write_minimal_jpeg(Path(tmp))
                    result = ingest_photos(
                        tmp,
                        device=self.DEVICE,
                        recursive=False,
                        calculate_checksum=False,
                        fix_errors=True,
                    )

                    assert result["errors_repair_attempted"] == 0

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_fix_errors_candidate_collection_uses_batched_db_lookup(
        self, *_mocks
    ) -> None:
        from photochart.ingest.photos import collect_error_repair_candidates

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    tmp_path = Path(tmp)
                    paths_on_disk = []
                    for i in range(5):
                        img = self._write_minimal_jpeg(tmp_path, f"p{i}.jpg")
                        paths_on_disk.append(img)
                    photograph = Photograph.objects.create(has_errors=True)
                    PhotoPath.objects.create(
                        path=str(paths_on_disk[0].resolve()),
                        device=self.DEVICE,
                        photograph=photograph,
                    )

                    with self.assertNumQueries(2):
                        candidates = collect_error_repair_candidates(
                            paths_on_disk,
                            self.DEVICE,
                            ingest_path=tmp,
                        )

                    assert len(candidates) == 1


class PhotographRepairFromFileTest(TestCase):
    def _write_minimal_jpeg(self, directory: Path) -> Path:
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
            b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
            b"\x1c $.\x27 ,#\x1c\x1c(7),01444\x1f\x27=9=82<.342\xff\xc0\x00\x0b\x08"
            b"\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01"
            b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06"
            b"\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05"
            b"\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
            b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17'
            b"\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85"
            b"\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5"
            b"\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5"
            b"\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4"
            b"\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5\x7f\xff\xd9"
        )
        path = directory / "photo.jpg"
        path.write_bytes(jpeg)
        return path

    @patch("photograph.models.Photograph.get_image_from_file", return_value=True)
    @patch("photograph.models.Photograph.compute_checksum_from_file")
    def test_repair_clears_has_errors_when_steps_succeed(
        self, mock_checksum, mock_thumb
    ) -> None:
        mock_checksum.return_value = "a" * 32

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    img = self._write_minimal_jpeg(Path(tmp))
                    photograph = Photograph.objects.create(has_errors=True)

                    ok = photograph.repair_from_file(
                        str(img.resolve()), store_thumbnail=True
                    )

                    assert ok is True
                    photograph.refresh_from_db()
                    assert photograph.has_errors is False
                    mock_checksum.assert_called_once()
                    mock_thumb.assert_called_once()


# ---------------------------------------------------------------------------
# Ingest pre-filter already catalogued
# ---------------------------------------------------------------------------


class IngestPrefilterCataloguedTest(TestCase):
    DEVICE = "test-device"

    def _write_minimal_jpeg(self, directory: Path, name: str = "photo.jpg") -> Path:
        jpeg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
            b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
            b"\x1c $.\x27 ,#\x1c\x1c(7),01444\x1f\x27=9=82<.342\xff\xc0\x00\x0b\x08"
            b"\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01"
            b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06"
            b"\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05"
            b"\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
            b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17'
            b"\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85"
            b"\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5"
            b"\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5"
            b"\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4"
            b"\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5\x7f\xff\xd9"
        )
        path = directory / name
        path.write_bytes(jpeg)
        return path

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_skips_already_catalogued_file(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    img = self._write_minimal_jpeg(Path(tmp))
                    path_str = str(img.resolve())
                    PhotoPath.objects.create(
                        path=path_str, device=self.DEVICE, photograph=None
                    )

                    result = ingest_photos(
                        tmp,
                        device=self.DEVICE,
                        recursive=False,
                        calculate_checksum=False,
                        store_images=False,
                    )

                    assert result["count"] == 0
                    assert result["skipped_already_ingested"] == 1
                    assert result["success"] is True
                    assert PhotoPath.objects.count() == 1

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_mixed_catalogued_and_new_files(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    tmp_path = Path(tmp)
                    existing = self._write_minimal_jpeg(tmp_path, "existing.jpg")
                    self._write_minimal_jpeg(tmp_path, "new.jpg")
                    PhotoPath.objects.create(
                        path=str(existing.resolve()),
                        device=self.DEVICE,
                        photograph=None,
                    )

                    result = ingest_photos(
                        tmp,
                        device=self.DEVICE,
                        recursive=False,
                        calculate_checksum=False,
                        store_images=False,
                    )

                    assert result["count"] == 1
                    assert result["skipped_already_ingested"] == 1
                    assert PhotoPath.objects.count() == 2

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_all_catalogued_still_succeeds(self, *_mocks) -> None:
        from photochart.ingest.photos import ingest_photos

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    tmp_path = Path(tmp)
                    a = self._write_minimal_jpeg(tmp_path, "a.jpg")
                    b = self._write_minimal_jpeg(tmp_path, "b.jpg")
                    for img in (a, b):
                        PhotoPath.objects.create(
                            path=str(img.resolve()),
                            device=self.DEVICE,
                            photograph=None,
                        )

                    result = ingest_photos(
                        tmp,
                        device=self.DEVICE,
                        recursive=False,
                        calculate_checksum=False,
                        store_images=False,
                    )

                    assert result["success"] is True
                    assert result["count"] == 0
                    assert result["skipped_already_ingested"] == 2
                    assert not any(
                        "No image files found" in e for e in result["errors"]
                    )

    @patch("photochart.ingest.photos.get_mount_point", return_value=None)
    @patch("photochart.ingest.photos.get_device_name", return_value=DEVICE)
    def test_ingest_loads_mount_table_once(self, *_mocks) -> None:
        from photochart.fs.device import load_mount_table as real_load_mount_table
        from photochart.ingest.photos import ingest_photos

        load_calls = 0

        def counting_load(*args, **kwargs):
            nonlocal load_calls
            load_calls += 1
            return real_load_mount_table(*args, **kwargs)

        with tempfile.TemporaryDirectory() as media_root:
            with tempfile.TemporaryDirectory() as tmp:
                with self.settings(MEDIA_ROOT=media_root):
                    tmp_path = Path(tmp)
                    for i in range(3):
                        self._write_minimal_jpeg(tmp_path, f"photo{i}.jpg")
                    catalogued = tmp_path / "photo0.jpg"
                    PhotoPath.objects.create(
                        path=str(catalogued.resolve()),
                        device=self.DEVICE,
                        photograph=None,
                    )

                    with patch(
                        "photochart.ingest.photos.load_mount_table",
                        side_effect=counting_load,
                    ):
                        result = ingest_photos(
                            tmp,
                            device=self.DEVICE,
                            recursive=False,
                            calculate_checksum=False,
                            store_images=False,
                        )

                    assert load_calls == 1
                    assert result["skipped_already_ingested"] == 1
                    assert result["count"] == 2


# ---------------------------------------------------------------------------
# Resize stored thumbnails
# ---------------------------------------------------------------------------


class ResizeStoredThumbnailTest(TestCase):
    def _minimal_jpeg_bytes(self) -> bytes:
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c"
            b"\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c"
            b"\x1c $.\x27 ,#\x1c\x1c(7),01444\x1f\x27=9=82<.342\xff\xc0\x00\x0b\x08"
            b"\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01"
            b"\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06"
            b"\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05"
            b"\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa"
            b'\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17'
            b"\x18\x19\x1a%&'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85"
            b"\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5"
            b"\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5"
            b"\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4"
            b"\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda"
            b"\x00\x08\x01\x01\x00\x00?\x00\xfb\xd5\x7f\xff\xd9"
        )

    def test_resize_stored_thumbnail_scales_image(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                photograph = Photograph.objects.create()
                photograph.thumbnail.save(
                    "large.jpg",
                    SimpleUploadedFile("large.jpg", self._minimal_jpeg_bytes()),
                    save=True,
                )
                assert photograph.resize_stored_thumbnail((32, 32)) is True
                photograph.refresh_from_db()
                with Image.open(photograph.thumbnail.path) as img:
                    assert max(img.size) <= 32

    def test_resize_all_thumbnails_respects_max_size(self) -> None:
        from photochart.catalog.resize_thumbnails import resize_all_thumbnails

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                small = Photograph.objects.create()
                small.thumbnail.save(
                    "small.jpg",
                    SimpleUploadedFile("small.jpg", b"x" * 100),
                    save=True,
                )
                large = Photograph.objects.create()
                large.thumbnail.save(
                    "large.jpg",
                    SimpleUploadedFile(
                        "large.jpg", self._minimal_jpeg_bytes() + (b"\x00" * 900_000)
                    ),
                    save=True,
                )

                with (
                    patch(
                        "photochart.catalog.resize_thumbnails._thumbnail_byte_size",
                        side_effect=lambda p: 100 if p.pk == small.pk else 900_000,
                    ),
                    patch.object(
                        Photograph, "resize_stored_thumbnail", return_value=True
                    ) as mock_resize,
                ):
                    result = resize_all_thumbnails("thumbnail", max_size="800K")

                assert result["success"] is True
                assert result["skipped_too_small"] == 1
                assert result["resized"] == 1
                assert mock_resize.call_count == 1


# ---------------------------------------------------------------------------
# Photograph list API – cursor pagination and count
# ---------------------------------------------------------------------------


class PhotographListApiTest(TestCase):
    def setUp(self) -> None:
        _make_reader("listuser")
        self.client.login(username="listuser", password="secret")

    def test_unknown_filter_returns_next_when_more_than_page_size(self) -> None:
        for _ in range(55):
            Photograph.objects.create(time=None)

        response = self.client.get("/api/photographs/?year=Unknown&ordering=id")
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 50
        assert data["next"] is not None

    def test_count_matches_unknown_filter(self) -> None:
        for _ in range(7):
            Photograph.objects.create(time=None)
        Photograph.objects.create()

        count_response = self.client.get("/api/photographs/count/?year=Unknown")
        assert count_response.status_code == 200
        assert count_response.json()["count"] == 7

    def test_ordering_id_asc_vs_desc(self) -> None:
        a = Photograph.objects.create(time=None)
        b = Photograph.objects.create(time=None)
        c = Photograph.objects.create(time=None)

        asc = self.client.get("/api/photographs/?year=Unknown&ordering=id")
        assert asc.status_code == 200
        asc_ids = [item["id"] for item in asc.json()["results"]]

        desc = self.client.get("/api/photographs/?year=Unknown&ordering=-id")
        assert desc.status_code == 200
        desc_ids = [item["id"] for item in desc.json()["results"]]

        assert asc_ids == sorted([a.id, b.id, c.id])
        assert desc_ids == sorted([a.id, b.id, c.id], reverse=True)


# ---------------------------------------------------------------------------
# Photo paths – directories API
# ---------------------------------------------------------------------------


class PhotoPathDirectoriesApiTest(TestCase):
    DEVICE = "pcloud"

    def setUp(self) -> None:
        _make_reader("pathuser")
        self.client.login(username="pathuser", password="secret")

    def test_directories_lists_all_root_segments_beyond_sample_limit(self) -> None:
        big_count = 1001
        other_count = 5
        rows = [
            PhotoPath(
                path=f"BigFolder/sub/{i}.jpg",
                device=self.DEVICE,
                filename=f"{i}.jpg",
            )
            for i in range(big_count)
        ] + [
            PhotoPath(
                path=f"OtherFolder/{i}.jpg",
                device=self.DEVICE,
                filename=f"{i}.jpg",
            )
            for i in range(other_count)
        ]
        PhotoPath.objects.bulk_create(rows, batch_size=500)

        response = self.client.get(
            f"/api/photo-paths/directories/?device={self.DEVICE}"
        )
        assert response.status_code == 200
        by_name = {item["name"]: item for item in response.json()}

        assert "BigFolder" in by_name
        assert "OtherFolder" in by_name
        assert by_name["BigFolder"]["is_directory"] is True
        assert by_name["OtherFolder"]["is_directory"] is True
        assert by_name["BigFolder"]["count"] == big_count
        assert by_name["OtherFolder"]["count"] == other_count

    def test_directories_with_path_prefix_lists_immediate_children(self) -> None:
        PhotoPath.objects.bulk_create(
            [
                PhotoPath(
                    path="Album/at_root.jpg",
                    device=self.DEVICE,
                    filename="at_root.jpg",
                ),
                PhotoPath(
                    path="Album/Sub/photo.jpg",
                    device=self.DEVICE,
                    filename="photo.jpg",
                ),
            ]
        )

        response = self.client.get(
            "/api/photo-paths/directories/",
            {"device": self.DEVICE, "path_prefix": "Album"},
        )
        assert response.status_code == 200
        by_name = {item["name"]: item for item in response.json()}

        assert by_name["at_root.jpg"]["is_directory"] is False
        assert by_name["at_root.jpg"]["count"] == 1
        assert by_name["Sub"]["is_directory"] is True
        assert by_name["Sub"]["count"] == 1
