from django.contrib import admin

from .models import (
    DuplicateGroup,
    DuplicateScan,
    OrganizerConfiguration,
    OrganizerJob,
    OrganizerLease,
    OrganizerOperation,
)

admin.site.register(OrganizerConfiguration)
admin.site.register(OrganizerJob)
admin.site.register(OrganizerLease)
admin.site.register(OrganizerOperation)
admin.site.register(DuplicateGroup)
admin.site.register(DuplicateScan)
