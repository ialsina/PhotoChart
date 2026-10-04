from collections.abc import Callable

from django.utils import timezone

from photochart.organizer.adapters import build_adapter
from photochart.organizer.config import (
    OrganizerConfig,
    RetryConfig,
    StabilityConfig,
)
from photochart.organizer.domain import OperationStatus
from photochart.organizer.service import Organizer

from .models import OrganizerJob, OrganizerOperation


class JobCancelled(Exception):
    pass


def _core_config(job: OrganizerJob) -> OrganizerConfig:
    stored = job.configuration
    return OrganizerConfig(
        source=stored.source,
        destination=stored.destination,
        adapter=stored.adapter,
        adapter_options=stored.adapter_options,
        pattern=stored.pattern,
        quarantine=stored.quarantine,
        mode=stored.mode,
        timezone=stored.timezone,
        collision=stored.collision,
        duplicate_detection=stored.duplicate_detection,
        workers=stored.workers,
        scan_interval_seconds=stored.scan_interval_seconds,
        process_after=stored.process_after,
        include_first=stored.include_first,
        day_starts_at=stored.day_starts_at,
        media_extensions=tuple(stored.media_extensions),
        date_priority=tuple(stored.date_priority),
        stability=StabilityConfig(**stored.stability),
        retry=RetryConfig(**stored.retry),
    )


def _catalog_local_result(result) -> None:
    if result.status not in {OperationStatus.COPIED, OperationStatus.MOVED}:
        return
    if not result.destination:
        return
    from photochart.ingest.photos import ingest_photos

    ingest_photos(
        result.destination,
        recursive=False,
        calculate_checksum=True,
        store_images=True,
    )


def _job_media(job: OrganizerJob, organizer: Organizer):
    sources = job.source_paths
    if job.retry_of_id:
        sources = list(
            job.retry_of.operations.filter(status="failed").values_list(
                "source", flat=True
            )
        )
    if not sources:
        return None
    return [organizer.adapter.get_object_info(source) for source in sources]


def execute_job(
    job: OrganizerJob, heartbeat: Callable[[], None] | None = None
) -> OrganizerJob:
    job.status = OrganizerJob.Status.RUNNING
    job.started_at = timezone.now()
    job.heartbeat_at = job.started_at
    job.error = ""
    job.save(update_fields=["status", "started_at", "heartbeat_at", "error"])
    try:
        if not job.configuration.enabled:
            raise ValueError("Organizer configuration is disabled")
        config = _core_config(job)
        organizer = Organizer(build_adapter(config), config)
        failed = False
        for result in organizer.iter_once(
            dry_run=job.dry_run,
            media_objects=_job_media(job, organizer),
        ):
            job.refresh_from_db(fields=["cancel_requested_at"])
            if job.cancel_requested_at:
                raise JobCancelled("Cancellation requested")
            catalog_status = "not_applicable"
            if not job.dry_run and result.status in {
                OperationStatus.COPIED,
                OperationStatus.MOVED,
            }:
                if config.adapter in {"local", "pcloud_drive"}:
                    _catalog_local_result(result)
                    catalog_status = "cataloged"
                else:
                    catalog_status = "manual_required"
            OrganizerOperation.objects.create(
                job=job,
                status=result.status.value,
                source=result.source,
                destination=result.destination,
                object_id=result.object_id,
                capture_date=(result.date_result.value if result.date_result else None),
                date_source=(result.date_result.source if result.date_result else ""),
                detail=result.detail or "",
                verified=result.verified,
                catalog_status=catalog_status,
            )
            failed = failed or result.status == OperationStatus.FAILED
            job.heartbeat_at = timezone.now()
            job.save(update_fields=["heartbeat_at"])
            if heartbeat:
                heartbeat()
        job.status = (
            OrganizerJob.Status.FAILED if failed else OrganizerJob.Status.COMPLETED
        )
    except JobCancelled as error:
        job.status = OrganizerJob.Status.CANCELLED
        job.error = str(error)
    except Exception as error:
        job.status = OrganizerJob.Status.FAILED
        job.error = str(error)
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error", "finished_at"])
    return job
