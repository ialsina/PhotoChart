"""API views for the planner app."""

from rest_framework import viewsets

from backend.permissions import IsPhotoChartOperator

from .models import PlannedAction
from .serializers import PlannedActionSerializer


class PlannedActionViewSet(viewsets.ModelViewSet):
    """ViewSet for viewing and editing PlannedAction instances."""

    queryset = PlannedAction.objects.all().select_related("photograph", "organizer_job")
    serializer_class = PlannedActionSerializer
    permission_classes = [IsPhotoChartOperator]
