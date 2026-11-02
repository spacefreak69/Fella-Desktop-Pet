from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from platformdirs import user_log_dir
from PySide6.QtCore import QObject, QPoint, QTimer, Qt
from PySide6.QtGui import QAction, QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from .assets import Assets, AssetsError, colors_dir
from .behavior.clicks import ClickCounter
from .behavior.mood import MoodController
from .behavior.perimeter import Rect, Track, build_patrol_track
from .behavior.policy import MODE_HIDE, MODE_OVERLAY, MODE_PATROL, decide_mode
from .behavior.wander import Wander
from .config import APP_NAME, Config, load_config, save_config
from .pet_window import PetWindow
from .tracking import TrackedWindow, create_tracker
from .tracking.base import matches_process
from .ui.settings_dialog import SettingsDialog

log = logging.getLogger(__name__)

PET_GAP_PX = 8
EDGE_MARGIN_PX = 4
INITIAL_MARGIN_PX = 24


def setup_logging() -> None:
    handlers: list[logging.Handler] = []
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    try:
        log_dir = Path(user_log_dir(APP_NAME, appauthor=False))
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                log_dir / "fella.log",
                maxBytes=512 * 1024,
                backupCount=2,
                encoding="utf-8",
            )
        )
    except OSError:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )


class FellaApp(QObject):
    def __init__(self, qt_app: QApplication) -> None:
        super().__init__()
        self._qt_app = qt_app
        self._qt_app.setQuitOnLastWindowClosed(False)

        self.config = load_config()
        self.assets = Assets(colors_dir(), self.config.scale)

        self.window = PetWindow(self.assets, self.config.always_on_top)
        self.window.clicked.connect(self._on_click)
        self.window.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.window.customContextMenuRequested.connect(self._show_menu)

        self.clicks = ClickCounter(
            self.config.clicks_for_pink, self.config.click_window_s
        )
        self.mood = MoodController(self.config, self)
        self.mood.state_changed.connect(self._on_state_changed)
        self.wander = Wander(self.window, self.config, self)
        self.tracker = create_tracker()
        self._own_pid = os.getpid()

        self._paused = False
        self._hidden_for_fullscreen = False
        self._shut_down = False

        self._track_timer = QTimer(self)
        self._track_timer.setInterval(int(self.config.tracker_poll_interval_s * 1000))
        self._track_timer.timeout.connect(self._poll_windows)

        self._overlay_timer = QTimer(self)
        self._overlay_timer.setInterval(1000)
        self._overlay_timer.timeout.connect(self.window.ensure_on_top)

        self._menu = QMenu()
        self._pause_action: QAction | None = None
        self._tray: QSystemTrayIcon | None = None
        self._setup_menu_and_tray()

        self._place_initially()
        self.window.show()
        self.window.raise_()

        self.mood.start()
        self.wander.start()
        self._track_timer.start()
        self._poll_windows()

    def _setup_menu_and_tray(self) -> None:
        settings_action = QAction("Settings...", self)
        settings_action.triggered.connect(self.open_settings)

        self._pause_action = QAction("Pause", self)
        self._pause_action.setCheckable(True)
        self._pause_action.toggled.connect(self.set_paused)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._qt_app.quit)

        self._menu.addAction(settings_action)
        self._menu.addAction(self._pause_action)
        self._menu.addSeparator()
        self._menu.addAction(quit_action)

        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("System tray is not available; right-click fella for the menu.")
            return
        tray = QSystemTrayIcon(QIcon(self.assets.pixmap(self.mood.state)), self)
        tray.setToolTip("fella")
        tray.setContextMenu(self._menu)
        tray.activated.connect(self._on_tray_activated)
        tray.show()
        self._tray = tray

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_settings()

    def _show_menu(self, position: QPoint) -> None:
        self._menu.popup(self.window.mapToGlobal(position))

    def _on_click(self) -> None:
        if self.clicks.register_click():
            self.mood.trigger_pink()

    def _on_state_changed(self, state: str) -> None:
        self.window.set_state(state)
        if self._tray is not None:
            self._tray.setIcon(QIcon(self.assets.pixmap(state)))

    def set_paused(self, paused: bool) -> None:
        paused = bool(paused)
        if paused == self._paused:
            return
        self._paused = paused
        self.wander.set_paused(paused)
        self.mood.set_paused(paused)
        if self._pause_action is not None and self._pause_action.isChecked() != paused:
            self._pause_action.setChecked(paused)
        if paused:
            self._leave_overlay()
            self.wander.set_patrol_track(None)
            self.wander.set_roam_bounds(None)
            self._show_after_fullscreen()
        else:
            self._poll_windows()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_config(dialog.result_config())

    def apply_config(self, new_config: Config) -> None:
        try:
            save_config(new_config)
        except OSError:
            log.warning("Could not save config", exc_info=True)
        self.config = new_config

        self.clicks.configure(new_config.clicks_for_pink, new_config.click_window_s)
        self.assets.set_scale(new_config.scale)
        self.window.refresh_assets()
        was_hidden = self._hidden_for_fullscreen
        self.window.set_always_on_top(new_config.always_on_top)
        if was_hidden:
            self.window.hide()
        self.window.move(self._clamp_to_screen(self.window.pos()))
        self.wander.sync_position()

        self.mood.apply_config(new_config)
        self.wander.apply_config(new_config)
        self._track_timer.setInterval(int(new_config.tracker_poll_interval_s * 1000))
        self._poll_windows()

    def _poll_windows(self) -> None:
        if self._paused or (
            not self.config.seek_doom and not self.config.fullscreen_overlay
        ):
            self._enter_roam()
            return

        foreground: TrackedWindow | None
        try:
            foreground = self.tracker.get_foreground_window()
        except Exception:
            log.warning("Foreground window scan failed", exc_info=True)
            foreground = None

        is_doom = foreground is not None and matches_process(
            foreground.process, self.config.doom_processes
        )
        mode = decide_mode(self.config, foreground, self._own_pid, is_doom)

        if mode == MODE_OVERLAY and foreground is not None:
            self._enter_overlay(foreground)
        elif mode == MODE_PATROL and foreground is not None:
            self._enter_patrol(foreground)
        elif mode == MODE_HIDE:
            self._enter_hidden()
        else:
            self._enter_roam()

    def _enter_overlay(self, target: TrackedWindow) -> None:
        self._show_after_fullscreen()
        self.window.set_overlay_mode(True)
        self.wander.set_patrol_track(None)
        self.wander.set_roam_bounds(
            Rect(
                left=float(target.x),
                top=float(target.y),
                width=float(target.width),
                height=float(target.height),
            )
        )
        self.window.ensure_on_top()
        if not self._overlay_timer.isActive():
            self._overlay_timer.start()
        log.debug("Overlaying fullscreen window %r", target.title)

    def _enter_patrol(self, target: TrackedWindow) -> None:
        self._leave_overlay()
        self._show_after_fullscreen()
        self.wander.set_roam_bounds(None)
        track = self._patrol_track_for(target)
        self.wander.set_patrol_track(track)
        log.debug("Patrolling window %r", target.title)

    def _enter_hidden(self) -> None:
        self._leave_overlay()
        self.wander.set_patrol_track(None)
        self.wander.set_roam_bounds(None)
        self._hide_for_fullscreen()

    def _enter_roam(self) -> None:
        self._leave_overlay()
        self.wander.set_patrol_track(None)
        self.wander.set_roam_bounds(None)
        self._show_after_fullscreen()

    def _leave_overlay(self) -> None:
        self._overlay_timer.stop()
        if self.window.overlay_mode:
            self.window.set_overlay_mode(False)

    def _patrol_track_for(self, target: TrackedWindow) -> Track | None:
        screen_rect = self._screen_rect_for(target)
        if screen_rect is None:
            return None
        window_rect = Rect(
            left=float(target.x),
            top=float(target.y),
            width=float(target.width),
            height=float(target.height),
        )
        return build_patrol_track(
            window_rect,
            self.window.width(),
            self.window.height(),
            screen_rect,
            gap=PET_GAP_PX,
            margin=EDGE_MARGIN_PX,
        )

    def _screen_rect_for(self, target: TrackedWindow) -> Rect | None:
        screen = QGuiApplication.screenAt(
            QPoint(target.x + target.width // 2, target.y + target.height // 2)
        )
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is None:
            return None
        geometry = screen.availableGeometry()
        return Rect(
            left=float(geometry.left()),
            top=float(geometry.top()),
            width=float(geometry.width()),
            height=float(geometry.height()),
        )

    def _clamp_to_screen(self, point: QPoint) -> QPoint:
        screens = QGuiApplication.screens()
        if not screens:
            return point
        width = self.window.width()
        height = self.window.height()
        probe = QPoint(point.x() + width // 2, point.y() + height // 2)
        screen = QGuiApplication.screenAt(probe)
        if screen is None:
            screen = min(
                screens,
                key=lambda candidate: (candidate.geometry().center().x() - probe.x())
                ** 2
                + (candidate.geometry().center().y() - probe.y()) ** 2,
            )
        geometry = screen.availableGeometry()
        min_x = geometry.left() + EDGE_MARGIN_PX
        min_y = geometry.top() + EDGE_MARGIN_PX
        max_x = geometry.left() + geometry.width() - width - EDGE_MARGIN_PX
        max_y = geometry.top() + geometry.height() - height - EDGE_MARGIN_PX
        x = min(max(point.x(), min_x), max(max_x, min_x))
        y = min(max(point.y(), min_y), max(max_y, min_y))
        return QPoint(x, y)

    def _place_initially(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geometry = screen.availableGeometry()
        width = self.window.width()
        height = self.window.height()
        self.window.move(
            geometry.left() + geometry.width() - width - INITIAL_MARGIN_PX,
            geometry.top() + geometry.height() - height - INITIAL_MARGIN_PX,
        )

    def _hide_for_fullscreen(self) -> None:
        if self.window.isVisible():
            self.window.hide()
            self._hidden_for_fullscreen = True

    def _show_after_fullscreen(self) -> None:
        if self._hidden_for_fullscreen:
            self._hidden_for_fullscreen = False
            self.window.show()
            self.window.raise_()

    def shutdown(self) -> None:
        if getattr(self, "_shut_down", False):
            return
        self._shut_down = True
        self._track_timer.stop()
        self._overlay_timer.stop()
        self.wander.stop()
        self.mood.stop()
        try:
            self.tracker.close()
        except Exception:
            pass
        if self._tray is not None:
            self._tray.hide()


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    app = QApplication(sys.argv if argv is None else argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    if sys.platform.startswith("linux") and app.platformName() == "wayland":
        log.warning(
            "Qt is running on Wayland, where windows cannot position themselves. "
            "Use QT_QPA_PLATFORM=xcb (XWayland) for roaming to work."
        )
    try:
        controller = FellaApp(app)
    except AssetsError as exc:
        log.error("%s", exc)
        QMessageBox.critical(None, "fella", str(exc))
        return 1
    except Exception:
        log.exception("fella failed to start")
        QMessageBox.critical(
            None, "fella", "fella failed to start. Check the log for details."
        )
        return 1
    try:
        return app.exec()
    finally:
        controller.shutdown()
