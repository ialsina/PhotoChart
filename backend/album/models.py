from django.db import models


class Album(models.Model):
    """Album model for organizing photographs into collections.

    Albums can contain multiple photographs, and photographs can belong
    to multiple albums (many-to-many relationship).
    """

    name = models.CharField(max_length=255, help_text="Name of the album")
    description = models.TextField(
        blank=True, help_text="Optional description of the album"
    )
    photos = models.ManyToManyField(
        "photograph.Photograph",
        related_name="albums",
        blank=True,
        help_text="Photographs in this album",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the album was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the album was last updated"
    )

    class Meta:
        verbose_name = "Album"
        verbose_name_plural = "Albums"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return self.name
