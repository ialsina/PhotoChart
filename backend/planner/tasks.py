"""Idempotent execution of approved planned actions."""

from pathlib import Path

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from photochart.fs.protocols import calculate_checksum

from organizer.models import OrganizerJob
from organizer.tasks import execute_job_task

from .models import PlannedAction


def _validated_local_paths(action: PlannedAction) -> list[Path]:
    if action.photograph is None:
        raise ValueError("The photograph no longer exists.")
    resolved: list[Path] = []
    for photo_path in action.photograph.paths.all():
        full_path = photo_path.get_full_path()
        if not full_path:
            raise ValueError(f"Cannot resolve catalog path {photo_path.path!r}.")
        path = Path(full_path)
        if not path.exists():
            continue
        if action.photograph.checksum:
            actual = calculate_checksum(str(path))
            if actual != action.photograph.checksum:
                raise ValueError(f"Checksum changed; refusing to delete {path}.")
        resolved.append(path)
    return resolved


def _create_job(action: PlannedAction) -> OrganizerJob:
    if action.action_type == PlannedAction.ActionType.RETRY:
        previous = action.organizer_job
        if previous is None:
            raise ValueError("RETRY action has no source job.")
        return OrganizerJob.objects.create(
            configuration=previous.configuration,
            dry_run=previous.dry_run,
            retry_of=previous,
        )

    configuration = action.organizer_configuration
    if configuration is None or action.photograph is None:
        raise ValueError("ORGANIZE action is missing its target.")
    if configuration.adapter not in {"local", "pcloud_drive"}:
        raise ValueError(
            "Catalog-planned ORGANIZE actions require a filesystem adapter."
        )
    source_paths = [
        full_path
        for photo_path in action.photograph.paths.all()
        if (full_path := photo_path.get_full_path())
    ]
    if not source_paths:
        raise ValueError("No resolvable source paths were found.")
    return OrganizerJob.objects.create(
        configuration=configuration,
        dry_run=False,
        source_paths=source_paths,
    )


@shared_task(bind=True, name="planner.execute_planned_action")
def execute_planned_action(self, action_id: int) -> str:
    with transaction.atomic():
        action = (
            PlannedAction.objects.select_for_update()
            .select_related(
                "photograph",
                "organizer_job__configuration",
                "organizer_configuration",
            )
            .get(pk=action_id)
        )
        if action.status != PlannedAction.Status.PENDING:
            return action.status
        action.status = PlannedAction.Status.RUNNING
        action.task_id = self.request.id or ""
        action.started_at = timezone.now()
        action.error = ""
        action.save(update_fields=["status", "task_id", "started_at", "error"])

    try:
        if action.action_type == PlannedAction.ActionType.DELETE:
            paths = _validated_local_paths(action)
            for path in paths:
                path.unlink()
            action.photograph.delete()
            action.photograph = None
        else:
            job = _create_job(action)
            action.result_job = job
            transaction.on_commit(lambda: execute_job_task.delay(job.pk))
        action.status = PlannedAction.Status.COMPLETED
    except Exception as error:
        action.status = PlannedAction.Status.FAILED
        action.error = str(error)
    action.finished_at = timezone.now()
    action.save(update_fields=["status", "result_job", "error", "finished_at"])
    return action.status
