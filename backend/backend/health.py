"""Liveness, readiness, metrics, and protected media endpoints."""

import hmac
import time
from pathlib import PurePosixPath
from urllib.parse import quote

import redis
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.db.models import Count
from django.http import Http404, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET
from prometheus_client import CollectorRegistry, Gauge, generate_latest

WORKER_HEARTBEAT_KEY = "photochart:worker:heartbeat"


@require_GET
def liveness(request):
    return JsonResponse({"status": "alive"})


@require_GET
def readiness(request):
    checks = {}
    try:
        connection.ensure_connection()
        checks["database"] = "available"
    except Exception:
        checks["database"] = "unavailable"
    try:
        client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        client.ping()
        heartbeat = client.get(WORKER_HEARTBEAT_KEY)
        worker_age = time.time() - float(heartbeat) if heartbeat else None
        checks["redis"] = "available"
        checks["worker"] = (
            "available" if worker_age is not None and worker_age <= 90 else "stale"
        )
    except Exception:
        checks["redis"] = "unavailable"
        checks["worker"] = "unavailable"
    ready = all(value == "available" for value in checks.values())
    return JsonResponse(
        {"status": "ready" if ready else "unavailable", **checks},
        status=200 if ready else 503,
    )


@require_GET
def metrics(request):
    expected = settings.METRICS_TOKEN
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not expected or not hmac.compare_digest(supplied, expected):
        return HttpResponse(status=403)

    from organizer.models import OrganizerJob, OrganizerOperation

    registry = CollectorRegistry()
    jobs = Gauge(
        "photochart_organizer_jobs",
        "Organizer jobs by status",
        ["status"],
        registry=registry,
    )
    for item in OrganizerJob.objects.values("status").annotate(count=Count("id")):
        jobs.labels(status=item["status"]).set(item["count"])
    failures = Gauge(
        "photochart_organizer_failed_operations",
        "Persisted failed organizer operations",
        registry=registry,
    )
    failures.set(OrganizerOperation.objects.filter(status="failed").count())
    return HttpResponse(
        generate_latest(registry),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )


@require_GET
@login_required
def protected_media(request, path):
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise Http404
    response = HttpResponse()
    response["X-Accel-Redirect"] = "/_protected_media/" + quote(
        candidate.as_posix(), safe="/"
    )
    return response
