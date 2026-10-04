"""Wait until Django's default database accepts connections."""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Wait for the configured default database to become available."

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout",
            type=float,
            default=60.0,
            help="Maximum number of seconds to wait before failing.",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=1.0,
            help="Seconds to sleep between connection attempts.",
        )

    def handle(self, *args, **options):
        timeout = options["timeout"]
        interval = options["interval"]
        deadline = time.monotonic() + timeout
        connection = connections[DEFAULT_DB_ALIAS]
        last_error: Exception | None = None

        while True:
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("Database is available."))
                return
            except OperationalError as exc:
                last_error = exc
                connection.close()

            if time.monotonic() >= deadline:
                raise CommandError(
                    f"Database did not become available within {timeout:g}s: {last_error}"
                )

            time.sleep(interval)
