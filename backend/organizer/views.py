from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from backend.permissions import IsPhotoChartOperator

from .models import (
    DuplicateGroup,
    OrganizerConfiguration,
    OrganizerJob,
    OrganizerOperation,
)
from .serializers import (
    DuplicateGroupSerializer,
    OrganizerConfigurationSerializer,
    OrganizerJobSerializer,
    OrganizerJobSummarySerializer,
    OrganizerOperationSerializer,
)
from .tasks import execute_job_task


@api_view(["GET"])
@permission_classes([AllowAny])
def organizer_health(request):
    connection.ensure_connection()
    return Response(
        {
            "status": "ready",
            "database": "available",
            "adapters": [
                "local",
                "pcloud_drive",
                "pcloud_api",
                "webdav",
                "nextcloud",
                "sftp",
                "s3",
            ],
        }
    )


class OrganizerConfigurationViewSet(viewsets.ModelViewSet):
    queryset = OrganizerConfiguration.objects.all().order_by("name")
    serializer_class = OrganizerConfigurationSerializer

    def get_permissions(self):
        permission = (
            IsAuthenticated
            if self.request.method in SAFE_METHODS
            else IsPhotoChartOperator
        )
        return [permission()]

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        configuration = self.get_object()
        if not configuration.enabled:
            return Response(
                {"detail": "Organizer configuration is disabled."},
                status=status.HTTP_409_CONFLICT,
            )
        job = OrganizerJob.objects.create(
            configuration=configuration,
            dry_run=bool(request.data.get("dry_run", True)),
        )
        transaction.on_commit(lambda: execute_job_task.delay(job.pk))
        return Response(
            OrganizerJobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED,
        )


class OrganizerJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        OrganizerJob.objects.select_related("configuration")
        .annotate(operation_count=Count("operations"))
        .order_by("-created_at")
    )
    serializer_class = OrganizerJobSerializer
    filterset_fields = ["configuration", "status", "dry_run"]

    def get_serializer_class(self):
        if self.action == "list":
            return OrganizerJobSummarySerializer
        return OrganizerJobSerializer

    def get_permissions(self):
        permission = (
            IsPhotoChartOperator
            if self.action in {"retry", "cancel"}
            else IsAuthenticated
        )
        return [permission()]

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        previous = self.get_object()
        if not previous.configuration.enabled:
            return Response(
                {"detail": "Organizer configuration is disabled."},
                status=status.HTTP_409_CONFLICT,
            )
        job = OrganizerJob.objects.create(
            configuration=previous.configuration,
            dry_run=previous.dry_run,
            retry_of=previous,
        )
        transaction.on_commit(lambda: execute_job_task.delay(job.pk))
        return Response(
            OrganizerJobSerializer(job).data,
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        job = self.get_object()
        if job.status not in {
            OrganizerJob.Status.PENDING,
            OrganizerJob.Status.RUNNING,
        }:
            return Response(
                {"detail": "Only pending or running jobs can be cancelled."},
                status=status.HTTP_409_CONFLICT,
            )
        job.cancel_requested_at = timezone.now()
        if job.status == OrganizerJob.Status.PENDING:
            job.status = OrganizerJob.Status.CANCELLED
            job.finished_at = timezone.now()
        job.save(update_fields=["cancel_requested_at", "status", "finished_at"])
        return Response(OrganizerJobSerializer(job).data)


class OrganizerOperationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrganizerOperation.objects.select_related("job")
    serializer_class = OrganizerOperationSerializer
    filterset_fields = ["job", "status", "verified"]


class DuplicateGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DuplicateGroup.objects.all()
    serializer_class = DuplicateGroupSerializer
