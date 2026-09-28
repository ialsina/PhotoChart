from django.utils import timezone

from photochart.organizer.adapters import build_adapter
from photochart.organizer.config import OrganizerConfig
from photochart.organizer.domain import OperationStatus
from photochart.organizer.service import Organizer

from .models import OrganizerJob, OrganizerOperation


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
    )


def _catalog_local_result(result) -> None:
    if result.status not in {OperationStatus.COPIED, OperationStatus.MOVED}:
        return
    if not result.destination:
        return
    from photochart.ingest import ingest_photos

    ingest_photos(
        result.destination,
        recursive=False,
        calculate_checksum=True,
        store_images=True,
    )


def execute_job(job: OrganizerJob) -> OrganizerJob:
    job.status = OrganizerJob.Status.RUNNING
    job.started_at = timezone.now()
    job.error = ""
    job.save(update_fields=["status", "started_at", "error"])
    try:
        config = _core_config(job)
        results = Organizer(build_adapter(config), config).run_once(dry_run=job.dry_run)
        operations = []
        for result in results:
            operations.append(
                OrganizerOperation(
                    job=job,
                    status=result.status.value,
                    source=result.source,
                    destination=result.destination,
                    capture_date=(
                        result.date_result.value if result.date_result else None
                    ),
                    date_source=(
                        result.date_result.source if result.date_result else ""
                    ),
                    detail=result.detail or "",
                    verified=result.verified,
                )
            )
            if not job.dry_run and config.adapter in {"local", "pcloud_drive"}:
                _catalog_local_result(result)
        OrganizerOperation.objects.bulk_create(operations)
        failed = any(result.status == OperationStatus.FAILED for result in results)
        job.status = (
            OrganizerJob.Status.FAILED if failed else OrganizerJob.Status.COMPLETED
        )
    except Exception as error:
        job.status = OrganizerJob.Status.FAILED
        job.error = str(error)
    job.finished_at = timezone.now()
    job.save(update_fields=["status", "error", "finished_at"])
    return job
