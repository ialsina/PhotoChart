"""Celery tasks for catalog ingest jobs."""

from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, name="photograph.run_ingest_job")
def run_ingest_job(self, job_id: int) -> str:
    """Execute an IngestJob: validate, dispatch local-or-Docker, persist results.

    Mirrors the ``organizer.execute_job`` pattern:
      1. Mark the job RUNNING and record the Celery task ID.
      2. Call ``photochart.ingest.runner.choose_and_run_ingest``.
      3. Update status fields and mark COMPLETED or FAILED.

    Args:
        job_id: Primary key of the ``IngestJob`` to run.

    Returns:
        Final status string (one of ``IngestJob.Status.*``).
    """
    from .models import IngestJob

    job = IngestJob.objects.get(pk=job_id)
    job.task_id = self.request.id or ""
    job.status = IngestJob.Status.RUNNING
    job.started_at = timezone.now()
    job.error = ""
    job.save(update_fields=["task_id", "status", "started_at", "error"])

    try:
        from photochart.ingest.runner import choose_and_run_ingest

        result = choose_and_run_ingest(
            path=job.path,
            mount_root=job.mount_root or None,
            device=job.device or None,
            recursive=job.recursive,
            calculate_checksum=job.calculate_checksum,
            store_images=job.store_images,
            resolution=job.resolution or None,
        )

        job.count = result.get("count", 0)
        job.checksums_calculated = result.get("checksums_calculated", 0)
        job.images_stored = result.get("images_stored", 0)

        errors = result.get("errors", [])
        if errors:
            job.error = "\n".join(errors)

        if result.get("success"):
            job.status = IngestJob.Status.COMPLETED
        else:
            job.status = IngestJob.Status.FAILED

    except Exception as exc:
        job.status = IngestJob.Status.FAILED
        job.error = str(exc)

    job.finished_at = timezone.now()
    job.save(
        update_fields=[
            "status",
            "error",
            "count",
            "checksums_calculated",
            "images_stored",
            "finished_at",
        ]
    )
    return job.status
