from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter
from PySide6.QtWidgets import QWidget

from .assets import Assets
from .config import BASE_STATES

log = logging.getLogger(__name__)

DRAG_THRESHOLD_PX = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_TRANSPARENT = 0x00000020
WS_EX_NOACTIVATE = 0x08000000
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200


class PetWindow(QWidget):
    clicked = Signal()
    drag_started = Signal()
    drag_finished = Signal()

    def __init__(self, assets: Assets, always_on_top: bool = True) -> None:
        super().__init__(None)
        self._assets = assets
        self._state = BASE_STATES[0]
        self._always_on_top = bool(always_on_top)
        self._pixmap = assets.pixmap(self._state)
        self._overlay = False

        self._drag_anchor: QPoint | None = None
        self._drag_window_origin = QPoint()
        self._press_global: QPoint | None = None
        self._dragging = False

        self.setWindowTitle("fella")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowFlags(self._flags())
        self.setFixedSize(self._pixmap.size())

    def _flags(self) -> Qt.WindowType:
        flags = (
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if self._always_on_top or self._overlay:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        if self._overlay:
            flags |= Qt.WindowType.WindowTransparentForInput
        return flags

    @property
    def state(self) -> str:
        return self._state

    @property
    def overlay_mode(self) -> bool:
        return self._overlay

    def set_state(self, state: str) -> None:
        pixmap = self._assets.pixmap(state)
        self._state = state
        if pixmap.size() != self.size():
            self.setFixedSize(pixmap.size())
        self._pixmap = pixmap
        self.update()

    def refresh_assets(self) -> None:
        pixmap = self._assets.pixmap(self._state)
        self._pixmap = pixmap
        self.setFixedSize(pixmap.size())
        self.update()

    def set_always_on_top(self, on_top: bool) -> None:
        on_top = bool(on_top)
        if on_top == self._always_on_top:
            return
        self._always_on_top = on_top
        if self._overlay:
            self._apply_win32_flags()
            return
        self.setWindowFlags(self._flags())
        self.show()
        self._apply_win32_flags()

    def set_overlay_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._overlay:
            return
        self._overlay = enabled
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, enabled)
        self.setWindowFlags(self._flags())
        self.show()
        self._apply_win32_flags()
        if enabled:
            self.ensure_on_top()

    def ensure_on_top(self) -> None:
        if not self._overlay or sys.platform != "win32":
            return
        try:
            user32 = ctypes.windll.user32
            user32.SetWindowPos.argtypes = [
                wintypes.HWND,
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                wintypes.UINT,
            ]
            user32.SetWindowPos.restype = wintypes.BOOL
            user32.SetWindowPos(
                wintypes.HWND(int(self.winId())),
                wintypes.HWND(HWND_TOPMOST),
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_NOOWNERZORDER,
            )
        except Exception:  # pragma: no cover - platform specific
            log.debug("Could not raise fella above the fullscreen app", exc_info=True)

    def is_dragging(self) -> bool:
        return self._dragging

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt naming
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(0, 0, self._pixmap)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt naming
        super().showEvent(event)
        self._apply_win32_flags()

    def contextMenuEvent(self, event) -> None:
        if self._overlay:
            event.ignore()
            return
        super().contextMenuEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._overlay:
            event.ignore()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._press_global = event.globalPosition().toPoint()
        self._drag_window_origin = self.pos()
        self._drag_anchor = self._press_global - self._drag_window_origin
        self._dragging = False
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._overlay:
            event.ignore()
            return
        if self._press_global is None or self._drag_anchor is None:
            return
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        current = event.globalPosition().toPoint()
        if not self._dragging:
            moved = (current - self._press_global).manhattanLength()
            if moved < DRAG_THRESHOLD_PX:
                return
            self._dragging = True
            self.drag_started.emit()
        self.move(current - self._drag_anchor)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._overlay:
            event.ignore()
            return
        if event.button() != Qt.MouseButton.LeftButton or self._press_global is None:
            super().mouseReleaseEvent(event)
            return
        was_dragging = self._dragging
        self._press_global = None
        self._drag_anchor = None
        self._dragging = False
        if was_dragging:
            self.drag_finished.emit()
        else:
            self.clicked.emit()
        event.accept()

    def _apply_win32_flags(self) -> None:
        if sys.platform != "win32":
            return
        try:
            user32 = ctypes.windll.user32
            hwnd = int(self.winId())
            if ctypes.sizeof(ctypes.c_void_p) == 8:
                get_long = user32.GetWindowLongPtrW
                set_long = user32.SetWindowLongPtrW
                get_long.argtypes = [wintypes.HWND, ctypes.c_int]
                get_long.restype = ctypes.c_ssize_t
                set_long.argtypes = [
                    wintypes.HWND,
                    ctypes.c_int,
                    ctypes.c_ssize_t,
                ]
                set_long.restype = ctypes.c_ssize_t
            else:
                get_long = user32.GetWindowLongW
                set_long = user32.SetWindowLongW
                get_long.argtypes = [wintypes.HWND, ctypes.c_int]
                get_long.restype = wintypes.LONG
                set_long.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
                set_long.restype = wintypes.LONG
            style = get_long(hwnd, GWL_EXSTYLE)
            style |= WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW
            if self._overlay:
                style |= WS_EX_TRANSPARENT
            else:
                style &= ~WS_EX_TRANSPARENT
            set_long(hwnd, GWL_EXSTYLE, style)
        except Exception:  # pragma: no cover - platform specific
            log.debug("Could not apply Win32 extended window styles", exc_info=True)
