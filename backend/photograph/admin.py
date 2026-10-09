from django.contrib import admin

from .models import Photograph, PhotoPath, StorageDevice, IngestJob


@admin.register(StorageDevice)
class StorageDeviceAdmin(admin.ModelAdmin):
    list_display = (
        "filesystem_uuid",
        "catalog_device",
        "vendor",
        "model",
        "serial",
        "capacity_bytes",
        "fstype",
        "probed_at",
    )
    search_fields = ("filesystem_uuid", "catalog_device", "serial", "vendor", "model")


@admin.register(PhotoPath)
class PhotoPathAdmin(admin.ModelAdmin):
    list_display = ("path", "device", "filesystem_uuid", "photograph", "created_at")
    list_filter = ("device",)
    search_fields = ("path", "device", "filesystem_uuid")


@admin.register(Photograph)
class PhotographAdmin(admin.ModelAdmin):
    list_display = ("id", "checksum", "time", "has_errors", "created_at")


@admin.register(IngestJob)
class IngestJobAdmin(admin.ModelAdmin):
    list_display = ("id", "path", "status", "update_device", "created_at")
