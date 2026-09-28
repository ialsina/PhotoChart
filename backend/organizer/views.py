from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

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


class OrganizerConfigurationViewSet(viewsets.ModelViewSet):
    queryset = OrganizerConfiguration.objects.all().order_by("name")
    serializer_class = OrganizerConfigurationSerializer

    @action(detail=True, methods=["post"])
    def run(self, request, pk=None):
        configuration = self.get_object()
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

    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        previous = self.get_object()
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
