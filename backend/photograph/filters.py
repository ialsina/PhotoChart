"""Shared photograph queryset filters for API list/count endpoints."""

from datetime import datetime

from django.db.models import QuerySet
from django.utils import timezone


def filter_photographs_by_navigation_params(
    queryset: QuerySet, query_params
) -> QuerySet:
    """Apply year/month/day navigation filters from query parameters."""
    year = query_params.get("year", None)

    if year and year != "Unknown":
        try:
            year_int = int(year)
            start_date = timezone.make_aware(datetime(year_int, 1, 1))
            end_date = timezone.make_aware(datetime(year_int + 1, 1, 1))
            queryset = queryset.filter(time__gte=start_date, time__lt=end_date)
        except (ValueError, TypeError):
            pass

    month = query_params.get("month", None)
    if month and year and year != "Unknown":
        try:
            year_int = int(year)
            month_int = int(month)
            start_date = timezone.make_aware(datetime(year_int, month_int, 1))
            if month_int == 12:
                end_date = timezone.make_aware(datetime(year_int + 1, 1, 1))
            else:
                end_date = timezone.make_aware(datetime(year_int, month_int + 1, 1))
            queryset = queryset.filter(time__gte=start_date, time__lt=end_date)
        except (ValueError, TypeError):
            pass

    day = query_params.get("day", None)
    if day and month and year and year != "Unknown":
        try:
            year_int = int(year)
            month_int = int(month)
            day_int = int(day)
            start_date = timezone.make_aware(datetime(year_int, month_int, day_int))
            end_date = timezone.make_aware(
                datetime(year_int, month_int, day_int, 23, 59, 59)
            )
            queryset = queryset.filter(time__gte=start_date, time__lte=end_date)
        except (ValueError, TypeError):
            pass

    if year == "Unknown":
        queryset = queryset.filter(time__isnull=True)

    return queryset


def photograph_list_ordering_tuple(ordering_param: str) -> tuple[str, ...]:
    """Map API ordering param to Django order_by fields (stable for cursor pagination)."""
    if ordering_param == "id":
        return ("id",)
    if ordering_param == "-id":
        return ("-id",)
    if ordering_param == "date":
        return ("display_time", "id")
    if ordering_param == "-date":
        return ("-display_time", "-id")
    return ("id",)


def photograph_list_needs_display_time_annotation(ordering_param: str) -> bool:
    return ordering_param in ("date", "-date")
