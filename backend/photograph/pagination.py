"""Pagination for photograph list endpoints."""

from rest_framework.pagination import CursorPagination


class PhotographCursorPagination(CursorPagination):
    """Cursor pagination for large photograph lists (stable ordering required)."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "id"

    def get_ordering(self, request, queryset, view):
        if hasattr(view, "get_photograph_list_ordering_tuple"):
            return view.get_photograph_list_ordering_tuple()
        if isinstance(self.ordering, str):
            return (self.ordering,)
        return self.ordering
