"""Celery application for durable background work."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

app = Celery("photochart")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
