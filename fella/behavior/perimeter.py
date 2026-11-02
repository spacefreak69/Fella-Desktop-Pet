from __future__ import annotations

from dataclasses import dataclass

DEFAULT_GAP_PX = 8
DEFAULT_MARGIN_PX = 4


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.left + self.width

    @property
    def bottom(self) -> float:
        return self.top + self.height

    @property
    def center(self) -> tuple[float, float]:
        return (self.left + self.width / 2.0, self.top + self.height / 2.0)


@dataclass(frozen=True)
class Track:
    """Rectangular path followed by the pet's top-left corner."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return max(0.0, self.right - self.left)

    @property
    def height(self) -> float:
        return max(0.0, self.bottom - self.top)

    @property
    def perimeter(self) -> float:
        return 2.0 * (self.width + self.height)

    def point_at(self, arc: float) -> tuple[float, float]:
        width = self.width
        height = self.height
        length = self.perimeter
        if length <= 0.0:
            return (self.left, self.top)
        position = arc % length

        if position < width:
            return (self.left + position, self.top)
        position -= width
        if position < height:
            return (self.right, self.top + position)
        position -= height
        if position < width:
            return (self.right - position, self.bottom)
        position -= width
        return (self.left, self.bottom - position)

    def nearest(self, x: float, y: float) -> tuple[float, float]:
        """Return (arc, distance) for the closest point on the path."""
        width = self.width
        height = self.height
        local_x = x - self.left
        local_y = y - self.top

        candidates: list[tuple[float, float]] = []

        top_x = _clamp(local_x, 0.0, width)
        candidates.append((top_x, _distance(local_x - top_x, local_y)))

        right_y = _clamp(local_y, 0.0, height)
        candidates.append(
            (width + right_y, _distance(local_x - width, local_y - right_y))
        )

        bottom_x = _clamp(local_x, 0.0, width)
        candidates.append(
            (
                width + height + (width - bottom_x),
                _distance(local_x - bottom_x, local_y - height),
            )
        )

        left_y = _clamp(local_y, 0.0, height)
        candidates.append(
            (
                2.0 * width + height + (height - left_y),
                _distance(local_x, local_y - left_y),
            )
        )

        return min(candidates, key=lambda candidate: candidate[1])

    def advance(self, arc: float, delta: float) -> float:
        length = self.perimeter
        if length <= 0.0:
            return 0.0
        return (arc + delta) % length


def build_patrol_track(
    window: Rect,
    pet_width: float,
    pet_height: float,
    screen: Rect,
    gap: float = DEFAULT_GAP_PX,
    margin: float = DEFAULT_MARGIN_PX,
) -> Track:
    """Build a path just outside a window, limited to the target screen."""
    left = window.left - pet_width - gap
    top = window.top - pet_height - gap
    right = window.left + window.width + gap
    bottom = window.top + window.height + gap

    min_x = screen.left + margin
    min_y = screen.top + margin
    max_x = max(min_x, screen.left + screen.width - pet_width - margin)
    max_y = max(min_y, screen.top + screen.height - pet_height - margin)

    left = _clamp(left, min_x, max_x)
    right = _clamp(right, min_x, max_x)
    top = _clamp(top, min_y, max_y)
    bottom = _clamp(bottom, min_y, max_y)

    if right - left < 1.0:
        center = (min_x + max_x) / 2.0
        left, right = center - 0.5, center + 0.5
    if bottom - top < 1.0:
        center = (min_y + max_y) / 2.0
        top, bottom = center - 0.5, center + 0.5

    return Track(left=left, top=top, right=right, bottom=bottom)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _distance(dx: float, dy: float) -> float:
    return (dx * dx + dy * dy) ** 0.5
