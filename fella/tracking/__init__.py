from __future__ import annotations

import logging
import os
import sys

from .base import NullTracker, TrackedWindow, WindowTracker

log = logging.getLogger(__name__)


def create_tracker() -> WindowTracker:
    if sys.platform == "win32":
        try:
            from .win32 import Win32Tracker

            return Win32Tracker()
        except Exception:  # pragma: no cover - platform specific
            log.warning("Win32 window tracking unavailable", exc_info=True)
            return NullTracker()

    if sys.platform.startswith("linux"):
        if not os.environ.get("DISPLAY"):
            log.warning(
                "No DISPLAY found; window tracking is disabled (Wayland is not supported)."
            )
            return NullTracker()
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            log.warning(
                "Wayland session: only XWayland clients are visible to the tracker; "
                "native Wayland games cannot be found."
            )
        try:
            from .x11 import X11Tracker

            return X11Tracker()
        except Exception:
            log.warning(
                "X11 window tracking unavailable (is python-xlib installed?)",
                exc_info=True,
            )
            return NullTracker()

    return NullTracker()


__all__ = ["TrackedWindow", "WindowTracker", "NullTracker", "create_tracker"]
