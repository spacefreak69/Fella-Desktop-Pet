from __future__ import annotations

import logging
import math
import random
import time
from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, QPointF, Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

from ..config import Config
from .perimeter import Rect, Track

log = logging.getLogger(__name__)

SCREEN_MARGIN_PX = 6
MAX_FRAME_DT_S = 0.25


def choose_screen_index(areas: Sequence[float], rng: random.Random) -> int:
    total = float(sum(max(0.0, area) for area in areas))
    if total <= 0.0:
        return 0
    threshold = rng.random() * total
    accumulated = 0.0
    for index, area in enumerate(areas):
        accumulated += max(0.0, area)
        if threshold <= accumulated:
            return index
    return len(areas) - 1


def choose_point_in_rect(
    rect: Rect,
    width: float,
    height: float,
    rng: random.Random,
    margin: float = SCREEN_MARGIN_PX,
) -> tuple[float, float]:
    min_x = rect.left + margin
    min_y = rect.top + margin
    max_x = max(min_x, rect.right - width - margin)
    max_y = max(min_y, rect.bottom - height - margin)
    return (rng.uniform(min_x, max_x), rng.uniform(min_y, max_y))


def clamp_point_to_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    rect: Rect,
    margin: float = SCREEN_MARGIN_PX,
) -> tuple[float, float]:
    min_x = rect.left + margin
    min_y = rect.top + margin
    max_x = max(min_x, rect.right - width - margin)
    max_y = max(min_y, rect.bottom - height - margin)
    return (min(max(x, min_x), max_x), min(max(y, min_y), max_y))


class Wander(QObject):
    """Moves the pet window randomly, along a window border, or inside a box."""

    def __init__(
        self,
        window: QWidget,
        config: Config,
        parent: QObject | None = None,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._config = config
        self._rng = rng or random.Random()
        self._clock = clock
        self._pos = QPointF(window.pos())
        self._target: QPointF | None = None
        self._idle_until = 0.0
        self._last_tick: float | None = None
        self._running = False
        self._paused = False

        self._roam_bounds: Rect | None = None
        self._patrol_track: Track | None = None
        self._patrol_arc = 0.0
        self._patrol_direction = 1
        self._patrol_approaching = False

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._tick)

        window.drag_started.connect(self._on_drag_started)
        window.drag_finished.connect(self._on_drag_finished)

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def roam_bounds(self) -> Rect | None:
        return self._roam_bounds

    @property
    def patrol_track(self) -> Track | None:
        return self._patrol_track

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._sync_position()
        self._last_tick = self._clock()
        if not self._paused:
            self._timer.start(self._interval_ms())

    def stop(self) -> None:
        self._running = False
        self._timer.stop()

    def set_paused(self, paused: bool) -> None:
        paused = bool(paused)
        if paused == self._paused:
            return
        self._paused = paused
        if paused:
            self._timer.stop()
        elif self._running:
            self._last_tick = self._clock()
            self._timer.start(self._interval_ms())

    def apply_config(self, config: Config) -> None:
        self._config = config
        if self._roam_bounds is not None:
            self._clamp_position_into_bounds()
        if self._running and not self._paused:
            self._timer.start(self._interval_ms())

    def set_patrol_track(self, track: Track | None) -> None:
        if track == self._patrol_track:
            return
        if track is None:
            had_patrol = self._patrol_track is not None
            self._patrol_track = None
            self._patrol_approaching = False
            if had_patrol:
                self._target = None
                self._idle_until = 0.0
            return

        self._roam_bounds = None
        if self._patrol_track is None:
            self._patrol_direction = self._rng.choice((-1, 1))
        self._patrol_track = track
        self._patrol_arc, _ = track.nearest(self._pos.x(), self._pos.y())
        self._patrol_approaching = True
        self._target = None
        self._idle_until = 0.0

    def set_roam_bounds(self, bounds: Rect | None) -> None:
        if bounds == self._roam_bounds:
            return
        had_bounds = self._roam_bounds is not None
        self._roam_bounds = bounds

        if bounds is None:
            if had_bounds:
                self._target = None
                self._idle_until = 0.0
            return

        self._patrol_track = None
        self._patrol_approaching = False
        self._target = None
        self._idle_until = 0.0
        self._clamp_position_into_bounds()

    def _interval_ms(self) -> int:
        return max(1, round(1000 / max(1, self._config.fps)))

    def sync_position(self) -> None:
        self._sync_position()

    def _sync_position(self) -> None:
        self._pos = QPointF(self._window.pos())

    def _on_drag_started(self) -> None:
        self._sync_position()
        self._target = None
        self._idle_until = 0.0

    def _on_drag_finished(self) -> None:
        self._sync_position()
        self._target = None
        self._idle_until = 0.0
        if self._patrol_track is not None:
            self._patrol_arc, _ = self._patrol_track.nearest(
                self._pos.x(), self._pos.y()
            )
            self._patrol_approaching = True
        elif self._roam_bounds is not None:
            self._clamp_position_into_bounds()

    def _tick(self) -> None:
        now = self._clock()
        if self._last_tick is None:
            self._last_tick = now
            return
        dt = min(max(now - self._last_tick, 0.0), MAX_FRAME_DT_S)
        self._last_tick = now

        if self._window.is_dragging():
            self._sync_position()
            self._target = None
            return

        if self._patrol_track is not None:
            self._tick_patrol(dt)
            return

        if self._target is None:
            if now < self._idle_until:
                return
            self._target = self._pick_target()
            if self._target is None:
                return

        assert self._target is not None
        delta = self._target - self._pos
        distance = math.hypot(delta.x(), delta.y())
        step = self._config.wander_speed_px_s * dt

        if distance <= step or distance == 0.0:
            self._pos = QPointF(self._target)
            self._apply_position()
            self._target = None
            self._idle_until = now + self._rng.uniform(
                self._config.idle_min_s, self._config.idle_max_s
            )
            return

        ratio = step / distance
        self._pos += QPointF(delta.x() * ratio, delta.y() * ratio)
        self._apply_position()

    def _tick_patrol(self, dt: float) -> None:
        track = self._patrol_track
        if track is None:
            return

        if self._patrol_approaching:
            target_x, target_y = track.point_at(self._patrol_arc)
            delta_x = target_x - self._pos.x()
            delta_y = target_y - self._pos.y()
            distance = math.hypot(delta_x, delta_y)
            step = self._config.wander_speed_px_s * dt
            if distance <= step or distance == 0.0:
                self._pos = QPointF(target_x, target_y)
                self._apply_position()
                self._patrol_approaching = False
                return
            ratio = step / distance
            self._pos += QPointF(delta_x * ratio, delta_y * ratio)
            self._apply_position()
            return

        delta = self._config.wander_speed_px_s * dt * self._patrol_direction
        self._patrol_arc = track.advance(self._patrol_arc, delta)
        target_x, target_y = track.point_at(self._patrol_arc)
        self._pos = QPointF(target_x, target_y)
        self._apply_position()

    def _pick_target(self) -> QPointF | None:
        width = self._window.width()
        height = self._window.height()

        if self._roam_bounds is not None:
            x, y = choose_point_in_rect(self._roam_bounds, width, height, self._rng)
            return QPointF(x, y)

        screens = QGuiApplication.screens()
        if not screens:
            return None
        geometries = [screen.availableGeometry() for screen in screens]
        areas = [max(1, geo.width() * geo.height()) for geo in geometries]
        geo = geometries[choose_screen_index(areas, self._rng)]
        bounds = Rect(
            left=float(geo.left()),
            top=float(geo.top()),
            width=float(geo.width()),
            height=float(geo.height()),
        )
        x, y = choose_point_in_rect(bounds, width, height, self._rng)
        return QPointF(x, y)

    def _clamp_position_into_bounds(self) -> None:
        if self._roam_bounds is None:
            return
        x, y = clamp_point_to_rect(
            self._pos.x(),
            self._pos.y(),
            self._window.width(),
            self._window.height(),
            self._roam_bounds,
        )
        if x == self._pos.x() and y == self._pos.y():
            return
        self._pos = QPointF(x, y)
        self._apply_position()

    def _apply_position(self) -> None:
        self._window.move(round(self._pos.x()), round(self._pos.y()))
