"""Small production middleware components."""

import re
import uuid

from .logging import request_id

VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,128}$")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Request-ID", "")
        identifier = (
            supplied if VALID_REQUEST_ID.fullmatch(supplied) else str(uuid.uuid4())
        )
        request_id.set(identifier)
        response = self.get_response(request)
        response["X-Request-ID"] = identifier
        return response
