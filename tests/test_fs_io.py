import errno

import pytest

from photochart.fs.io import (
    ReadRetryConfig,
    is_retryable_read_error,
    read_bytes_with_retry,
    with_read_retry,
)


def test_is_retryable_read_error() -> None:
    assert is_retryable_read_error(OSError(errno.EIO, "io error"))
    assert not is_retryable_read_error(PermissionError("denied"))
    assert not is_retryable_read_error(OSError(errno.EACCES, "denied"))


def test_read_bytes_with_retry_succeeds(tmp_path) -> None:
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(b"jpeg-bytes")

    data = read_bytes_with_retry(
        str(file_path),
        config=ReadRetryConfig(attempts=2, initial_seconds=0),
        sleep_fn=lambda _: None,
    )
    assert data == b"jpeg-bytes"


def test_read_bytes_with_retry_retries_incomplete_read(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(b"abcdefghij")

    reads = 0
    real_open = open

    def flaky_open(path, mode="rb", *args, **kwargs):
        nonlocal reads
        handle = real_open(path, mode, *args, **kwargs)
        if "b" not in mode:
            return handle

        class Wrapper:
            def __init__(self, inner):
                self._inner = inner

            def read(self, size=-1):
                nonlocal reads
                reads += 1
                if reads == 1:
                    return self._inner.read(4)
                return self._inner.read(size)

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                self._inner.close()

        return Wrapper(handle)

    monkeypatch.setattr("builtins.open", flaky_open)

    data = read_bytes_with_retry(
        str(file_path),
        config=ReadRetryConfig(attempts=3, initial_seconds=0),
        sleep_fn=lambda _: None,
    )

    assert data == b"abcdefghij"
    assert reads >= 2


def test_read_bytes_with_retry_waits_for_nonzero_size(tmp_path) -> None:
    import time

    file_path = tmp_path / "photo.jpg"
    file_path.write_bytes(b"")

    def hydrate_soon() -> None:
        time.sleep(0.05)
        file_path.write_bytes(b"ready")

    import threading

    threading.Thread(target=hydrate_soon, daemon=True).start()

    data = read_bytes_with_retry(
        str(file_path),
        config=ReadRetryConfig(
            attempts=6,
            initial_seconds=0.03,
            multiplier=1.0,
            stability_checks=1,
        ),
    )

    assert data == b"ready"


def test_with_read_retry_eventually_succeeds() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise OSError(errno.EIO, "try again")
        return "ok"

    result = with_read_retry(
        operation,
        config=ReadRetryConfig(attempts=4, initial_seconds=0),
        sleep_fn=lambda _: None,
    )
    assert result == "ok"
    assert calls == 3


def test_with_read_retry_does_not_retry_permission_error() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise PermissionError("denied")

    with pytest.raises(PermissionError):
        with_read_retry(
            operation,
            config=ReadRetryConfig(attempts=4, initial_seconds=0),
            sleep_fn=lambda _: None,
        )
    assert calls == 1
