from django.db import models


class PlannedAction(models.Model):
    """Planned action model for scheduling actions on photographs.

    Represents actions that are planned to be performed on photographs,
    such as deletion or other future operations.
    """

    class ActionType(models.TextChoices):
        """Action type choices for planned actions."""

        DELETE = "DELETE", "Delete"

    action_type = models.CharField(
        max_length=50,
        choices=ActionType.choices,
        help_text="Type of action to be performed",
    )
    photograph = models.ForeignKey(
        "photograph.Photograph",
        on_delete=models.CASCADE,
        related_name="planned_actions",
        help_text="Photograph this action applies to",
    )
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
        return f"{self.get_action_type_display()} for {self.photograph}"
