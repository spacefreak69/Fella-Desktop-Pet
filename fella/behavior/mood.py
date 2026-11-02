from __future__ import annotations

import random
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from ..config import BASE_STATES, PINK_STATE, Config


def pick_mood(current: str, rng: random.Random) -> str:
    choices = [state for state in BASE_STATES if state != current]
    if not choices:
        choices = list(BASE_STATES)
    return rng.choice(choices)


class MoodController(QObject):
    """Cycles through base colors and applies a temporary pink override."""

    state_changed = Signal(str)

    def __init__(
        self,
        config: Config,
        parent: QObject | None = None,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._rng = rng or random.Random()
        self._clock = clock
        self._state = BASE_STATES[0]
        self._pink = False
        self._running = False
        self._paused = False

        self._mood_timer = QTimer(self)
        self._mood_timer.setSingleShot(True)
        self._mood_timer.timeout.connect(self._advance_mood)

        self._pink_timer = QTimer(self)
        self._pink_timer.setSingleShot(True)
        self._pink_timer.timeout.connect(self._end_pink)

    @property
    def state(self) -> str:
        return PINK_STATE if self._pink else self._state

    @property
    def is_pink(self) -> bool:
        return self._pink

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._state = self._rng.choice(list(BASE_STATES))
        self.state_changed.emit(self._state)
        if not self._paused:
            self._schedule_mood()

    def stop(self) -> None:
        self._running = False
        self._mood_timer.stop()
        self._pink_timer.stop()

    def set_paused(self, paused: bool) -> None:
        paused = bool(paused)
        if paused == self._paused:
            return
        self._paused = paused
        if paused:
            self._mood_timer.stop()
            self._pink_timer.stop()
        elif self._running:
            if self._pink:
                self._end_pink()
            else:
                self._schedule_mood()

    def apply_config(self, config: Config) -> None:
        self._config = config

    def trigger_pink(self) -> None:
        if not self._running:
            return
        self._pink = True
        self._mood_timer.stop()
        self.state_changed.emit(PINK_STATE)
        self._pink_timer.start(int(self._config.pink_duration_s * 1000))

    def _end_pink(self) -> None:
        self._pink = False
        self._pink_timer.stop()
        self.state_changed.emit(self._state)
        if self._running and not self._paused:
            self._schedule_mood()

    def _advance_mood(self) -> None:
        if not self._running or self._paused or self._pink:
            return
        self._state = pick_mood(self._state, self._rng)
        self.state_changed.emit(self._state)
        self._schedule_mood()

    def _schedule_mood(self) -> None:
        low = self._config.mood_interval_min_s
        high = self._config.mood_interval_max_s
        delay_s = self._rng.uniform(low, high)
        self._mood_timer.start(max(250, int(delay_s * 1000)))
