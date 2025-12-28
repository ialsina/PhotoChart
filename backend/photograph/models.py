"""Photograph models for managing photo files and their paths.

This module provides Django models for storing photograph metadata,
including file hashes and image references, as well as tracking
photo paths across different devices.
"""

from django.db import models
from django.core.validators import RegexValidator


class Photograph(models.Model):
    """Photograph model storing photo metadata.
    
    Represents a photograph with optional hash and image file.
    The hash can be computed using the calculate_hash function from
    photofinder.protocols.
    """
    hash = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        help_text="MD5 hash of the photo file (32 characters)",
        validators=[
            RegexValidator(
                regex=r'^[a-f0-9]{32}$',
                message='Hash must be a 32-character hexadecimal string'
            )
        ]
    )
    image = models.ImageField(
        upload_to='photographs/',
        null=True,
        blank=True,
        help_text="Image file for the photograph"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the photograph record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the photograph record was last updated"
    )
    
    class Meta:
        verbose_name = 'Photograph'
        verbose_name_plural = 'Photographs'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['hash']),
        ]
    
    def __str__(self):
        if self.hash:
            return f"Photograph ({self.hash[:8]}...)"
        elif self.image:
            return f"Photograph ({self.image.name})"
        else:
            return f"Photograph (id: {self.id})"
    
    def compute_hash_from_image(self):
        """Compute and set the hash from the image file if available.
        
        Uses the calculate_hash function from photofinder.protocols.
        
        Returns:
            The computed hash string, or None if computation fails
        """
        if self.image and self.image.path:
            from photofinder.protocols import calculate_hash
            hash_value = calculate_hash(self.image.path)
            if hash_value:
                self.hash = hash_value
                self.save(update_fields=['hash'])
            return hash_value
        return None


class PhotoPath(models.Model):
    """Photo path model tracking file locations across devices.
    
    Represents a file path where a photograph exists, associated with
    a device and optionally linked to a Photograph instance.
    """
    path = models.CharField(
        max_length=2048,
        help_text="Full path to the photo file"
    )
    device = models.CharField(
        max_length=255,
        help_text="Device identifier where the photo is located"
    )
    photograph = models.ForeignKey(
        Photograph,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paths',
        help_text="Associated photograph (optional)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the path record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the path record was last updated"
    )
    
    class Meta:
        verbose_name = 'Photo Path'
        verbose_name_plural = 'Photo Paths'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['path']),
            models.Index(fields=['device']),
            models.Index(fields=['photograph']),
        ]
        unique_together = [['path', 'device']]
    
    def __str__(self):
        return f"{self.path} on {self.device}"
