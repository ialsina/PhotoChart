import pytest

from photochart.organizer.config import RetryConfig
from photochart.organizer.domain import ErrorKind, OrganizerError
from photochart.organizer.policies import with_retry


def test_retry_retries_transient_failures() -> None:
    attempts = 0

    def operation() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise OrganizerError("temporary", ErrorKind.TRANSIENT)
        return "ok"

    result = with_retry(
        operation,
        RetryConfig(attempts=3, initial_seconds=0),
        sleep=lambda _: None,
    )

    assert result == "ok"
    assert attempts == 3


@pytest.mark.parametrize(
    "error",
    [
        FileExistsError("conflict"),
        OrganizerError("invalid", ErrorKind.PERMANENT),
    ],
)
def test_retry_does_not_retry_permanent_failures(error: Exception) -> None:
    attempts = 0

    def operation() -> None:
        nonlocal attempts
        attempts += 1
        raise error

    with pytest.raises(type(error)):
        with_retry(
            operation,
            RetryConfig(attempts=3, initial_seconds=0),
            sleep=lambda _: None,
        )

    assert attempts == 1
