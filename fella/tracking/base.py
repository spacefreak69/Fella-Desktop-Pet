from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class TrackedWindow:
    handle: int
    title: str
    process: str
    x: int
    y: int
    width: int
    height: int
    minimized: bool = False
    fullscreen: bool = False
    foreground: bool = False
    pid: int | None = None

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)


class WindowTracker(Protocol):
    def get_windows(self, process_names: Sequence[str]) -> list[TrackedWindow]: ...

    def get_foreground_window(self) -> TrackedWindow | None: ...

    def close(self) -> None: ...


class NullTracker:
    def get_windows(self, process_names: Sequence[str]) -> list[TrackedWindow]:
        return []

    def get_foreground_window(self) -> TrackedWindow | None:
        return None

    def close(self) -> None:
        return None


def process_stem(name: str) -> str:
    stem = Path(name.replace("\\", "/")).name.lower()
    if stem.endswith(".exe"):
        stem = stem[: -len(".exe")]
    return stem


def matches_process(process: str, process_names: Sequence[str]) -> bool:
    stem = process_stem(process)
    if not stem:
        return False
    return any(stem == process_stem(candidate) for candidate in process_names)
