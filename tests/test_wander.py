import random

from PySide6.QtCore import QObject, QPoint, Signal

from fella.behavior.perimeter import Rect, Track
from fella.behavior.wander import (
    Wander,
    choose_point_in_rect,
    choose_screen_index,
    clamp_point_to_rect,
)
from fella.config import Config


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeWindow(QObject):
    drag_started = Signal()
    drag_finished = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._pos = QPoint(0, 0)
        self._width = 32
        self._height = 32
        self._dragging = False

    def pos(self) -> QPoint:
        return self._pos

    def move(self, x: int, y: int) -> None:
        self._pos = QPoint(x, y)

    def width(self) -> int:
        return self._width

    def height(self) -> int:
        return self._height

    def is_dragging(self) -> bool:
        return self._dragging


def test_choose_point_in_rect_stays_inside_bounds():
    rect = Rect(left=100.0, top=200.0, width=300.0, height=150.0)
    rng = random.Random(3)
    for _ in range(200):
        x, y = choose_point_in_rect(rect, 32.0, 32.0, rng, margin=6.0)
        assert 106.0 <= x <= rect.right - 32.0 - 6.0
        assert 206.0 <= y <= rect.bottom - 32.0 - 6.0


def test_clamp_point_to_rect_handles_edges_and_small_areas():
    rect = Rect(left=0.0, top=0.0, width=100.0, height=100.0)
    assert clamp_point_to_rect(50.0, 50.0, 20.0, 20.0, rect) == (50.0, 50.0)
    assert clamp_point_to_rect(-10.0, 200.0, 20.0, 20.0, rect) == (6.0, 74.0)

    tiny = Rect(left=0.0, top=0.0, width=10.0, height=10.0)
    assert clamp_point_to_rect(5.0, 5.0, 32.0, 32.0, tiny) == (6.0, 6.0)


def test_choose_screen_ignores_zero_area_screens():
    rng = random.Random(0)
    for _ in range(50):
        assert choose_screen_index([0, 0, 100], rng) == 2


def test_choose_screen_handles_all_zero():
    assert choose_screen_index([0, 0], random.Random(0)) == 0


def test_choose_screen_respects_area_weights():
    rng = random.Random(7)
    picks = [choose_screen_index([1, 1000], rng) for _ in range(500)]
    assert picks.count(1) > picks.count(0)
    assert set(picks) == {0, 1}


def test_patrol_advances_along_track():
    clock = FakeClock()
    window = FakeWindow()
    wander = Wander(
        window,
        Config(wander_speed_px_s=20.0, fps=60),
        rng=random.Random(0),
        clock=clock,
    )
    wander.set_patrol_track(Track(left=0.0, top=0.0, right=100.0, bottom=100.0))
    wander._patrol_direction = 1

    wander._tick()
    clock.now = 0.1
    wander._tick()
    clock.now = 0.6
    wander._tick()
    assert (window.pos().x(), window.pos().y()) == (5, 0)
    clock.now = 1.1
    wander._tick()
    assert (window.pos().x(), window.pos().y()) == (10, 0)


def test_roam_bounds_clamp_and_keep_targets_inside():
    clock = FakeClock()
    window = FakeWindow()
    wander = Wander(
        window,
        Config(wander_speed_px_s=100.0, fps=60, idle_min_s=0.0, idle_max_s=0.0),
        rng=random.Random(0),
        clock=clock,
    )
    bounds = Rect(left=50.0, top=60.0, width=200.0, height=150.0)
    wander.set_roam_bounds(bounds)
    assert (window.pos().x(), window.pos().y()) == (56, 66)

    wander._tick()
    for step in range(1, 200):
        clock.now = step * 0.1
        wander._tick()
        x, y = window.pos().x(), window.pos().y()
        assert 56 <= x <= 212
        assert 66 <= y <= 172

    wander.set_roam_bounds(None)
    assert wander.roam_bounds is None
