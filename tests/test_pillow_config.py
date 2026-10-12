"""Tests for Pillow decompression-bomb configuration."""

from __future__ import annotations

import importlib

import pytest
from PIL import Image

from photochart.imaging.pillow_config import (
    configure_pillow_once,
    parse_max_image_pixels,
    reset_pillow_configure_state_for_tests,
    resolve_pillow_pixel_limits,
)

_PILLOW_DEFAULT_MAX = int(1024 * 1024 * 1024 / 4 / 3)


@pytest.fixture(autouse=True)
def _reset_pillow_state() -> None:
    reset_pillow_configure_state_for_tests()
    Image.MAX_IMAGE_PIXELS = _PILLOW_DEFAULT_MAX
    yield
    reset_pillow_configure_state_for_tests()
    Image.MAX_IMAGE_PIXELS = _PILLOW_DEFAULT_MAX


class TestParseMaxImagePixels:
    def test_empty_and_null_leave_default(self) -> None:
        assert parse_max_image_pixels(None) is None
        assert parse_max_image_pixels("") is None
        assert parse_max_image_pixels("   ") is None
        assert parse_max_image_pixels("null") is None
        assert parse_max_image_pixels("NULL") is None

    def test_positive_integer(self) -> None:
        assert parse_max_image_pixels("500000000") == 500_000_000

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="positive integer"):
            parse_max_image_pixels("not-a-number")
        with pytest.raises(ValueError, match="positive"):
            parse_max_image_pixels("0")
        with pytest.raises(ValueError, match="positive"):
            parse_max_image_pixels("-1")


class TestConfigurePillowOnce:
    def test_disable_sets_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENABLE_MAX_IMAGE_PIXELS", "false")
        monkeypatch.delenv("MAX_IMAGE_PIXELS", raising=False)
        import photochart.imaging.pillow_config as pillow_config

        importlib.reload(pillow_config)
        pillow_config.reset_pillow_configure_state_for_tests()
        pillow_config.configure_pillow_once()
        assert Image.MAX_IMAGE_PIXELS is None

    def test_custom_max(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENABLE_MAX_IMAGE_PIXELS", "true")
        monkeypatch.setenv("MAX_IMAGE_PIXELS", "100")
        import photochart.imaging.pillow_config as pillow_config

        importlib.reload(pillow_config)
        pillow_config.reset_pillow_configure_state_for_tests()
        pillow_config.configure_pillow_once()
        assert Image.MAX_IMAGE_PIXELS == 100

    def test_unset_max_keeps_pillow_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENABLE_MAX_IMAGE_PIXELS", "true")
        monkeypatch.delenv("MAX_IMAGE_PIXELS", raising=False)
        import photochart.imaging.pillow_config as pillow_config

        importlib.reload(pillow_config)
        pillow_config.reset_pillow_configure_state_for_tests()
        Image.MAX_IMAGE_PIXELS = 12345
        pillow_config.configure_pillow_once()
        assert Image.MAX_IMAGE_PIXELS == 12345

    def test_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ENABLE_MAX_IMAGE_PIXELS", "true")
        monkeypatch.setenv("MAX_IMAGE_PIXELS", "200")
        import photochart.imaging.pillow_config as pillow_config

        importlib.reload(pillow_config)
        pillow_config.reset_pillow_configure_state_for_tests()
        pillow_config.configure_pillow_once()
        Image.MAX_IMAGE_PIXELS = 999
        pillow_config.configure_pillow_once()
        assert Image.MAX_IMAGE_PIXELS == 999


def test_resolve_without_django_uses_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENABLE_MAX_IMAGE_PIXELS", "true")
    monkeypatch.setenv("MAX_IMAGE_PIXELS", "42")
    enable, max_px = resolve_pillow_pixel_limits()
    assert enable is True
    assert max_px == 42
