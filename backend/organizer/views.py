from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from django.db import connection

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
    OrganizerOperationSerializer,
)
from .services import execute_job


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
        execute_job(job)
        return Response(
            OrganizerJobSerializer(job).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizerJobViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrganizerJob.objects.select_related("configuration").prefetch_related(
        "operations"
    )
    serializer_class = OrganizerJobSerializer

    def get_permissions(self):
        permission = IsPhotoChartOperator if self.action == "retry" else IsAuthenticated
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
        )
        execute_job(job)
        return Response(
            OrganizerJobSerializer(job).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizerOperationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrganizerOperation.objects.select_related("job")
    serializer_class = OrganizerOperationSerializer
    filterset_fields = ["job", "status", "verified"]


class DuplicateGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DuplicateGroup.objects.all()
    serializer_class = DuplicateGroupSerializer
