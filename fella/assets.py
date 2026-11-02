from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QSize

from .config import BASE_STATES, PINK_STATE, STATES


class AssetsError(RuntimeError):
    pass


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def colors_dir() -> Path:
    override = os.environ.get("FELLA_COLORS")
    if override:
        return Path(override)
    frozen = getattr(sys, "frozen", False)
    candidates: list[Path] = []
    if frozen:
        candidates.append(Path(sys.executable).resolve().parent / "colors")
    candidates.append(resource_root() / "colors")
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


class Assets:
    """Loads one sprite per state and keeps nearest-neighbour scaled copies."""

    def __init__(self, directory: Path, scale: int) -> None:
        self._dir = Path(directory)
        self._scale = max(1, int(scale))
        self._sources: dict[str, QPixmap] = {}
        self._scaled: dict[str, QPixmap] = {}
        self.reload()

    @property
    def directory(self) -> Path:
        return self._dir

    @property
    def scale(self) -> int:
        return self._scale

    def reload(self) -> None:
        missing: list[str] = []
        sources: dict[str, QPixmap] = {}
        for state in STATES:
            path = self._dir / f"{state}.png"
            if not path.is_file():
                missing.append(path.name)
                continue
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                missing.append(path.name)
                continue
            sources[state] = pixmap
        if missing:
            listed = ", ".join(missing)
            raise AssetsError(
                f"Missing or unreadable sprite(s) in {self._dir}: {listed}"
            )
        self._sources = sources
        self._rescale()

    def set_scale(self, scale: int) -> None:
        scale = max(1, int(scale))
        if scale == self._scale:
            return
        self._scale = scale
        self._rescale()

    def _rescale(self) -> None:
        self._scaled = {
            state: pixmap.scaled(
                pixmap.width() * self._scale,
                pixmap.height() * self._scale,
                Qt.AspectRatioMode.IgnoreAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            for state, pixmap in self._sources.items()
        }

    def pixmap(self, state: str) -> QPixmap:
        try:
            return self._scaled[state]
        except KeyError:  # pragma: no cover - defensive
            return self._scaled[BASE_STATES[0]]

    def size(self, state: str) -> QSize:
        return self.pixmap(state).size()

    def base_size(self, state: str = PINK_STATE) -> QSize:
        pixmap = self._sources[state]
        return QSize(pixmap.width(), pixmap.height())
