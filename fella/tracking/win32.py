from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes
from typing import Sequence

import psutil

from .base import TrackedWindow, matches_process

log = logging.getLogger(__name__)

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
MONITOR_DEFAULTTOPRIMARY = 1
MONITOR_DEFAULTTONEAREST = 2
FULLSCREEN_TOLERANCE_PX = 8


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", wintypes.LONG),
        ("top", wintypes.LONG),
        ("right", wintypes.LONG),
        ("bottom", wintypes.LONG),
    ]


class MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
    ]


_WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


class Win32Tracker:
    def __init__(self) -> None:
        if sys.platform != "win32":
            raise OSError("Win32Tracker is only available on Windows")
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._process_cache: dict[int, str] = {}

        user32 = self._user32
        user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.IsWindowVisible.restype = wintypes.BOOL
        user32.IsIconic.argtypes = [wintypes.HWND]
        user32.IsIconic.restype = wintypes.BOOL
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND,
            ctypes.POINTER(wintypes.DWORD),
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        user32.GetMonitorInfoW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(MONITORINFO),
        ]
        user32.GetMonitorInfoW.restype = wintypes.BOOL
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        else:
            user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.GetWindowLongW.restype = wintypes.LONG

    def get_windows(self, process_names: Sequence[str]) -> list[TrackedWindow]:
        results: list[TrackedWindow] = []
        foreground = self._user32.GetForegroundWindow()
        self._process_cache = {}

        def callback(hwnd, _lparam) -> bool:
            try:
                info = self._describe(hwnd, foreground)
            except Exception:  # pragma: no cover - defensive
                log.debug("Failed to inspect window %s", hwnd, exc_info=True)
                return True
            if info is not None and matches_process(info.process, process_names):
                results.append(info)
            return True

        self._user32.EnumWindows(_WNDENUMPROC(callback), 0)
        return results

    def get_foreground_window(self) -> TrackedWindow | None:
        self._process_cache = {}
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return None
        try:
            return self._describe(hwnd, hwnd)
        except Exception:  # pragma: no cover - defensive
            log.debug("Failed to inspect foreground window", exc_info=True)
            return None

    def _describe(self, hwnd: int, foreground: int) -> TrackedWindow | None:
        if not self._user32.IsWindowVisible(hwnd):
            return None
        minimized = bool(self._user32.IsIconic(hwnd))

        rect = RECT()
        if not self._user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        if width <= 0 or height <= 0:
            return None

        pid = wintypes.DWORD()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return None
        process = self._process_name(pid.value)

        title = self._window_title(hwnd)
        fullscreen = self._is_fullscreen(hwnd, rect)
        return TrackedWindow(
            handle=int(hwnd),
            title=title,
            process=process,
            x=rect.left,
            y=rect.top,
            width=width,
            height=height,
            minimized=minimized,
            fullscreen=fullscreen,
            foreground=int(hwnd) == int(foreground),
            pid=int(pid.value),
        )

    def _window_title(self, hwnd: int) -> str:
        length = self._user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        return buffer.value

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

    def _is_fullscreen(self, hwnd: int, rect: RECT) -> bool:
        monitor = self._user32.MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
        if not monitor:
            return False
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not self._user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        mon = info.rcMonitor
        return (
            abs(rect.left - mon.left) <= FULLSCREEN_TOLERANCE_PX
            and abs(rect.top - mon.top) <= FULLSCREEN_TOLERANCE_PX
            and abs(rect.right - mon.right) <= FULLSCREEN_TOLERANCE_PX
            and abs(rect.bottom - mon.bottom) <= FULLSCREEN_TOLERANCE_PX
        )

    def close(self) -> None:
        return None
