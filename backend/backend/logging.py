"""Logging context shared by Django requests and worker code."""

import contextvars
import logging

request_id = contextvars.ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id.get()
        return True
