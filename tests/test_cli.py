import importlib


def test_non_database_command_does_not_initialize_django(monkeypatch) -> None:
    cli_main = importlib.import_module("cli.main")

    def fail() -> None:
        raise AssertionError("Django should not be initialized")

    monkeypatch.setattr(cli_main, "_setup_django", fail)

    assert cli_main.main(["list-resolutions"]) == 0
