from __future__ import annotations

import logging
from typing import Sequence

import psutil

from .base import TrackedWindow, matches_process

log = logging.getLogger(__name__)


class X11Tracker:
    """EWMH-based window tracker for X11 (including XWayland clients)."""

    def __init__(self) -> None:
        from Xlib import X, display  # noqa: N811 - module name

        self._X = X
        self._display = display.Display()
        self._root = self._display.screen().root
        self._utf8 = self._display.intern_atom("UTF8_STRING")
        self._atom = {
            name: self._display.intern_atom(name)
            for name in (
                "_NET_CLIENT_LIST",
                "_NET_ACTIVE_WINDOW",
                "_NET_WM_PID",
                "_NET_WM_STATE",
                "_NET_WM_STATE_HIDDEN",
                "_NET_WM_STATE_FULLSCREEN",
                "_NET_WM_NAME",
            )
        }
        self._process_cache: dict[int, str] = {}

    def get_windows(self, process_names: Sequence[str]) -> list[TrackedWindow]:
        self._process_cache = {}
        if not process_names:
            return []
        results: list[TrackedWindow] = []
        active = self._first_cardinal(self._root, self._atom["_NET_ACTIVE_WINDOW"])
        for window_id in self._property_values(
            self._root, self._atom["_NET_CLIENT_LIST"]
        ):
            try:
                info = self._describe(window_id, active)
            except Exception:
                log.debug("Failed to inspect X11 window %s", window_id, exc_info=True)
                continue
            if info is not None and matches_process(info.process, process_names):
                results.append(info)
        return results

    def get_foreground_window(self) -> TrackedWindow | None:
        self._process_cache = {}
        active = self._first_cardinal(self._root, self._atom["_NET_ACTIVE_WINDOW"])
        if not active:
            return None
        try:
            return self._describe(active, active)
        except Exception:
            log.debug("Failed to inspect active X11 window", exc_info=True)
            return None

    def _describe(self, window_id: int, active: int) -> TrackedWindow | None:
        window = self._display.create_resource_object("window", window_id)
        pid = self._first_cardinal(window, self._atom["_NET_WM_PID"])
        process = self._process_name(pid) if pid else ""

        geometry = window.get_geometry()
        coords = self._root.translate_coords(window, 0, 0)
        states = set(self._atom_names(window, self._atom["_NET_WM_STATE"]))

        return TrackedWindow(
            handle=int(window_id),
            title=self._title(window),
            process=process,
            x=int(coords.x),
            y=int(coords.y),
            width=int(geometry.width),
            height=int(geometry.height),
            minimized="_NET_WM_STATE_HIDDEN" in states,
            fullscreen="_NET_WM_STATE_FULLSCREEN" in states,
            foreground=int(window_id) == int(active),
            pid=int(pid) if pid else None,
        )

    def _property_values(self, window, atom: int) -> list[int]:
        prop = window.get_full_property(atom, self._X.AnyPropertyType)
        if prop is None or prop.value is None:
            return []
        return [int(value) for value in prop.value]

    def _first_cardinal(self, window, atom: int) -> int:
        values = self._property_values(window, atom)
        return values[0] if values else 0

    def _atom_names(self, window, atom: int) -> list[str]:
        names: list[str] = []
        for value in self._property_values(window, atom):
            try:
                names.append(self._display.get_atom_name(value))
            except Exception:
                continue
        return names

    def _title(self, window) -> str:
        try:
            prop = window.get_full_property(self._atom["_NET_WM_NAME"], self._utf8)
            if prop is not None and prop.value:
                value = prop.value
                if isinstance(value, (bytes, bytearray)):
                    return value.decode("utf-8", "replace")
                return str(value)
        except Exception:
            pass
        try:
            name = window.get_wm_name()
            if isinstance(name, (bytes, bytearray)):
                return name.decode("latin-1", "replace")
            return str(name or "")
        except Exception:
            return ""

    def _process_name(self, pid: int) -> str:
        cached = self._process_cache.get(pid)
        if cached is not None:
            return cached
        try:
            name = psutil.Process(pid).name()
        except (psutil.Error, OSError):
            name = ""
        self._process_cache[pid] = name
        return name

    def close(self) -> None:
        try:
            self._display.close()
        except Exception:
            pass
