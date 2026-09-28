"""Safe classification path patterns."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import PurePosixPath


TOKENS = {
    "Y": lambda value: f"{value.year:04d}",
    "M": lambda value: f"{value.month:02d}",
    "D": lambda value: f"{value.day:02d}",
    "Q": lambda value: str((value.month - 1) // 3 + 1),
    "%": lambda value: "%",
}


@dataclass(frozen=True)
class ClassificationPattern:
    """Render capture dates into safe relative storage paths."""

    template: str = "%Y/%YQ%Q/%Y%M%D"

    def __post_init__(self) -> None:
        self._render(date(2000, 1, 1))

    def render(self, value: date | datetime) -> str:
        return self._render(value)

    def _render(self, value: date | datetime) -> str:
        output: list[str] = []
        index = 0
        while index < len(self.template):
            character = self.template[index]
            if character != "%":
                output.append(character)
                index += 1
                continue
            if index + 1 >= len(self.template):
                raise ValueError("Classification pattern ends with an incomplete token")
            token = self.template[index + 1]
            renderer = TOKENS.get(token)
            if renderer is None:
                raise ValueError(f"Unknown classification token: %{token}")
            output.append(renderer(value))
            index += 2

        rendered = "".join(output).replace("\\", "/")
        path = PurePosixPath(rendered)
        if not rendered or path.is_absolute() or ".." in path.parts:
            raise ValueError("Classification pattern must produce a safe relative path")
        if any(part in ("", ".") for part in path.parts):
            raise ValueError("Classification pattern contains an empty path component")
        return str(path)
