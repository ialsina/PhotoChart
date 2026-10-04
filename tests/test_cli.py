import importlib
import pytest


def test_non_database_command_does_not_initialize_django(monkeypatch) -> None:
    cli_main = importlib.import_module("cli.main")

    def fail() -> None:
        raise AssertionError("Django should not be initialized")

    monkeypatch.setattr(cli_main, "_setup_django", fail)

    assert cli_main.main(["list-resolutions"]) == 0


def test_resize_thumbnails_initializes_django(monkeypatch) -> None:
    cli_main = importlib.import_module("cli.main")

    called = {"value": False}

    def mark_setup() -> None:
        called["value"] = True

    monkeypatch.setattr(cli_main, "_setup_django", mark_setup)
    monkeypatch.setattr(
        "photochart.catalog.resize_thumbnails.resize_all_thumbnails",
        lambda **kwargs: {
            "success": True,
            "resized": 0,
            "skipped_too_small": 0,
            "skipped_no_thumbnail": 0,
            "failed": 0,
            "errors": [],
        },
    )

    assert cli_main.main(["resize-thumbnails", "--resolution", "medium"]) == 0
    assert called["value"] is True


def test_resize_thumbnails_requires_resolution() -> None:
    cli_main = importlib.import_module("cli.main")
    with pytest.raises(SystemExit):
        cli_main.main(["resize-thumbnails"])
