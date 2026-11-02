from __future__ import annotations

from ..config import Config
from ..tracking.base import TrackedWindow

MODE_ROAM = "roam"
MODE_PATROL = "patrol"
MODE_OVERLAY = "overlay"
MODE_HIDE = "hide"


def decide_mode(
    config: Config,
    foreground: TrackedWindow | None,
    own_pid: int,
    is_doom: bool,
) -> str:
    if foreground is None:
        return MODE_ROAM
    if foreground.pid is not None and foreground.pid == own_pid:
        return MODE_ROAM
    if config.fullscreen_overlay and foreground.fullscreen and not foreground.minimized:
        return MODE_OVERLAY
    if config.seek_doom and is_doom and not foreground.minimized:
        if foreground.fullscreen:
            return MODE_HIDE
        return MODE_PATROL
    return MODE_ROAM
