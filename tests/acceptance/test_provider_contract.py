"""Credentialed provider contract tests.

These tests mutate only the explicitly configured acceptance prefix and are
skipped unless all required environment variables are present.
"""

import os
import posixpath
import uuid

import pytest

from photochart.organizer.adapters import build_adapter
from photochart.organizer.collision import streams_equal
from photochart.organizer.config import load_config
from photochart.organizer.verify import verified_transfer

pytestmark = pytest.mark.integration

SUPPORTED_PROVIDERS = (
    "local",
    "pcloud_drive",
    "pcloud_api",
    "webdav",
    "nextcloud",
    "sftp",
    "s3",
)


@pytest.mark.parametrize("provider", SUPPORTED_PROVIDERS)
def test_provider_copy_verify_move_cleanup(provider):
    selected = os.environ.get("PHOTOCHART_ACCEPTANCE_PROVIDER")
    if selected != provider:
        pytest.skip(f"{provider} acceptance is not enabled")

    config_path = os.environ.get("PHOTOCHART_ACCEPTANCE_CONFIG")
    fixture = os.environ.get("PHOTOCHART_ACCEPTANCE_SOURCE_OBJECT")
    prefix = os.environ.get("PHOTOCHART_ACCEPTANCE_PREFIX")
    if not all((config_path, fixture, prefix)):
        pytest.skip("acceptance configuration is incomplete")

    config = load_config(config_path)
    assert config.adapter == provider
    adapter = build_adapter(config)
    run_prefix = posixpath.join(prefix, f"run-{uuid.uuid4().hex}")
    staged = posixpath.join(run_prefix, "staged.bin")
    moved = posixpath.join(run_prefix, "moved.bin")

    adapter.healthcheck()
    adapter.ensure_directory(run_prefix)
    try:
        adapter.copy(fixture, staged)
        assert streams_equal(adapter, fixture, staged)

        verified_transfer(adapter, staged, moved, delete_source=True)

        assert not adapter.exists(staged)
        assert streams_equal(adapter, fixture, moved)
    finally:
        for path in (staged, moved):
            if adapter.exists(path):
                adapter.delete(path)
