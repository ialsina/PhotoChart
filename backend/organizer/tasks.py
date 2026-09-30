"""Durable organizer tasks and database-backed single-flight leases."""

from datetime import timedelta
import time

import redis
from celery import shared_task
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from photochart.organizer.adapters import build_adapter
from photochart.organizer.reports import find_duplicates

from .models import DuplicateGroup, DuplicateScan, OrganizerJob, OrganizerLease
from .services import _core_config, execute_job


def _lease_deadline():
    seconds = getattr(settings, "ORGANIZER_LEASE_SECONDS", 86400)
    return timezone.now() + timedelta(seconds=seconds)


def acquire_lease(job: OrganizerJob) -> bool:
    with transaction.atomic():
        lease, _ = OrganizerLease.objects.select_for_update().get_or_create(
            configuration=job.configuration
        )
        if (
            lease.owner_job_id
            and lease.owner_job_id != job.pk
            and lease.locked_until
            and lease.locked_until > timezone.now()
        ):
            return False
        lease.owner_job = job
        lease.heartbeat_at = timezone.now()
        lease.locked_until = _lease_deadline()
        lease.save(update_fields=["owner_job", "heartbeat_at", "locked_until"])
        return True


def heartbeat_lease(job: OrganizerJob) -> None:
    OrganizerLease.objects.filter(
        configuration=job.configuration, owner_job=job
    ).update(heartbeat_at=timezone.now(), locked_until=_lease_deadline())


def release_lease(job: OrganizerJob) -> None:
    OrganizerLease.objects.filter(
        configuration=job.configuration, owner_job=job
    ).update(owner_job=None, heartbeat_at=None, locked_until=None)


@shared_task(bind=True, name="organizer.execute_job")
def execute_job_task(self, job_id: int) -> str:
    job = OrganizerJob.objects.select_related("configuration").get(pk=job_id)
    job.task_id = self.request.id or ""
    job.worker_id = self.request.hostname or ""
    job.save(update_fields=["task_id", "worker_id"])
    if not acquire_lease(job):
        job.status = OrganizerJob.Status.FAILED
        job.error = "Another job holds the organizer configuration lease."
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
        return job.status
    try:
        execute_job(job, heartbeat=lambda: heartbeat_lease(job))
        return job.status
    finally:
        release_lease(job)


@shared_task(name="organizer.recover_stale_jobs")
def recover_stale_jobs() -> int:
    cutoff = timezone.now() - timedelta(
        seconds=getattr(settings, "ORGANIZER_STALE_JOB_SECONDS", 900)
    )
    stale = OrganizerJob.objects.filter(
        status=OrganizerJob.Status.RUNNING,
        heartbeat_at__lt=cutoff,
    )
    recovered = 0
    for job in stale.select_related("configuration"):
        job.status = OrganizerJob.Status.FAILED
        job.error = "Worker heartbeat expired; job marked stale."
        job.finished_at = timezone.now()
        job.save(update_fields=["status", "error", "finished_at"])
        release_lease(job)
        recovered += 1
    return recovered


@shared_task(name="organizer.worker_heartbeat")
def worker_heartbeat() -> float:
    value = time.time()
    client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
    client.set("photochart:worker:heartbeat", value, ex=120)
    return value


@shared_task(bind=True, name="organizer.scan_duplicates")
def scan_duplicates(self, scan_id: int) -> str:
    scan = DuplicateScan.objects.select_related("configuration").get(pk=scan_id)
    scan.status = DuplicateScan.Status.RUNNING
    scan.task_id = self.request.id or ""
    scan.started_at = timezone.now()
    scan.error = ""
    scan.save(update_fields=["status", "task_id", "started_at", "error"])
    try:
        probe_job = OrganizerJob(configuration=scan.configuration)
        config = _core_config(probe_job)
        groups = find_duplicates(build_adapter(config), config.source)
        with transaction.atomic():
            DuplicateGroup.objects.filter(configuration=scan.configuration).delete()
            DuplicateGroup.objects.bulk_create(
                [
                    DuplicateGroup(
                        configuration=scan.configuration,
                        scan=scan,
                        checksum=group.checksum,
                        size=group.size,
                        paths=list(group.paths),
                        wasted_bytes=group.wasted_bytes,
                    )
                    for group in groups
                ]
            )
        scan.status = DuplicateScan.Status.COMPLETED
    except Exception as error:
        scan.status = DuplicateScan.Status.FAILED
        scan.error = str(error)
    scan.finished_at = timezone.now()
    scan.save(update_fields=["status", "error", "finished_at"])
    return scan.status
