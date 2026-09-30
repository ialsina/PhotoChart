"""Shared API authorization policies."""

from rest_framework.permissions import BasePermission


class IsPhotoChartOperator(BasePermission):
    """Allow mutations only to explicitly authorized operators."""

    message = "PhotoChart operator permission is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_superuser or user.has_perm("organizer.operate_organizer"))
        )
