"""API views for the planner app."""

from django.db import transaction
from django.utils import timezone
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from backend.permissions import IsPhotoChartOperator

from .models import PlannedAction
from .serializers import PlannedActionSerializer
from .tasks import execute_planned_action


class PlannedActionViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing PlannedAction instances."""

    queryset = PlannedAction.objects.all().select_related("photograph", "organizer_job")
    serializer_class = PlannedActionSerializer
    permission_classes = [IsPhotoChartOperator]

    def perform_create(self, serializer):
        planned_action = serializer.save()
        transaction.on_commit(lambda: execute_planned_action.delay(planned_action.pk))

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        planned_action = self.get_object()
        if planned_action.status != PlannedAction.Status.PENDING:
            return Response(
                {"detail": "Only pending actions can be cancelled."},
                status=status.HTTP_409_CONFLICT,
            )
        planned_action.status = PlannedAction.Status.CANCELLED
        planned_action.finished_at = timezone.now()
        planned_action.save(update_fields=["status", "finished_at"])
        return Response(self.get_serializer(planned_action).data)
