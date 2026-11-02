from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class ClickCounter:
    """Counts clicks inside a rolling time window and fires on threshold."""

    def __init__(
        self,
        threshold: int = 5,
        window_s: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._threshold = max(1, int(threshold))
        self._window_s = max(0.0, float(window_s))
        self._clock = clock
        self._clicks: deque[float] = deque()

    def configure(self, threshold: int, window_s: float) -> None:
        self._threshold = max(1, int(threshold))
        self._window_s = max(0.0, float(window_s))

    def register_click(self) -> bool:
        now = self._clock()
        cutoff = now - self._window_s
        while self._clicks and self._clicks[0] <= cutoff:
            self._clicks.popleft()
        self._clicks.append(now)
        if len(self._clicks) >= self._threshold:
            self._clicks.clear()
            return True
        return False

    def reset(self) -> None:
        self._clicks.clear()

    @property
    def count(self) -> int:
        return len(self._clicks)

    @property
    def threshold(self) -> int:
        return self._threshold
