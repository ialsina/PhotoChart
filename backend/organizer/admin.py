from django.contrib import admin

from .models import (
    DuplicateGroup,
    OrganizerConfiguration,
    OrganizerJob,
    OrganizerOperation,
)

admin.site.register(OrganizerConfiguration)
admin.site.register(OrganizerJob)
admin.site.register(OrganizerOperation)
admin.site.register(DuplicateGroup)
