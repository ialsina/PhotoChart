import uuid

from django.db import models


class PlannedAction(models.Model):
    """Planned action model for scheduling actions on photographs.

    Represents actions that are planned to be performed on photographs,
    such as deletion or other future operations.
    """

    class ActionType(models.TextChoices):
        """Action type choices for planned actions."""

        DELETE = "DELETE", "Delete"
        ORGANIZE = "ORGANIZE", "Organize"
        RETRY = "RETRY", "Retry"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"
        CANCELLED = "CANCELLED", "Cancelled"

    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        help_text="Type of action to be performed",
    )
    photograph = models.ForeignKey(
        "photograph.Photograph",
        on_delete=models.SET_NULL,
        related_name="planned_actions",
        help_text="Photograph this action applies to",
        null=True,
        blank=True,
    )
    organizer_job = models.ForeignKey(
        "organizer.OrganizerJob",
        on_delete=models.CASCADE,
        related_name="planned_actions",
        null=True,
        blank=True,
    )
    result_job = models.ForeignKey(
        "organizer.OrganizerJob",
        on_delete=models.SET_NULL,
        related_name="resulting_planned_actions",
        null=True,
        blank=True,
    )
    organizer_configuration = models.ForeignKey(
        "organizer.OrganizerConfiguration",
        on_delete=models.PROTECT,
        related_name="planned_actions",
        null=True,
        blank=True,
    )
    idempotency_key = models.UUIDField(default=uuid.uuid4, unique=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    task_id = models.CharField(max_length=255, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the planned action was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the planned action was last updated"
    )

    class Meta:
        verbose_name = "Planned Action"
        verbose_name_plural = "Planned Actions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action_type"]),
            models.Index(fields=["photograph"]),
        ]

    def __str__(self):
        target = self.photograph or self.organizer_job
        return f"{self.get_action_type_display()} for {target}"
