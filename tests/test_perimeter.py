import pytest

from fella.behavior.perimeter import Rect, Track, build_patrol_track


def test_track_point_at_corners_and_edges():
    track = Track(left=0.0, top=0.0, right=10.0, bottom=5.0)
    assert track.perimeter == 30.0
    assert track.point_at(0.0) == (0.0, 0.0)
    assert track.point_at(5.0) == (5.0, 0.0)
    assert track.point_at(10.0) == (10.0, 0.0)
    assert track.point_at(12.0) == (10.0, 2.0)
    assert track.point_at(15.0) == (10.0, 5.0)
    assert track.point_at(20.0) == (5.0, 5.0)
    assert track.point_at(25.0) == (0.0, 5.0)
    assert track.point_at(28.0) == (0.0, 2.0)
    assert track.point_at(30.0) == (0.0, 0.0)
    assert track.point_at(-1.0) == (0.0, 1.0)


def test_track_nearest_projects_onto_each_edge():
    track = Track(left=0.0, top=0.0, right=10.0, bottom=5.0)
    assert track.nearest(5.0, -3.0) == pytest.approx((5.0, 3.0))
    assert track.nearest(13.0, 2.0) == pytest.approx((12.0, 3.0))
    assert track.nearest(5.0, 8.0) == pytest.approx((20.0, 3.0))
    assert track.nearest(-2.0, 2.0) == pytest.approx((28.0, 2.0))


def test_track_advance_wraps_both_directions():
    track = Track(left=0.0, top=0.0, right=10.0, bottom=5.0)
    assert track.advance(29.0, 2.0) == pytest.approx(1.0)
    assert track.advance(1.0, -2.0) == pytest.approx(29.0)


def test_build_patrol_track_sits_outside_window():
    track = build_patrol_track(
        Rect(left=100.0, top=100.0, width=200.0, height=100.0),
        pet_width=30.0,
        pet_height=30.0,
        screen=Rect(left=0.0, top=0.0, width=800.0, height=600.0),
        gap=8.0,
        margin=4.0,
    )
    assert (track.left, track.top, track.right, track.bottom) == (
        62.0,
        62.0,
        308.0,
        208.0,
    )


def test_build_patrol_track_clamps_to_screen_edges():
    track = build_patrol_track(
        Rect(left=-50.0, top=-50.0, width=200.0, height=100.0),
        pet_width=30.0,
        pet_height=30.0,
        screen=Rect(left=0.0, top=0.0, width=800.0, height=600.0),
        gap=8.0,
        margin=4.0,
    )
    assert track.left == 4.0
    assert track.top == 4.0
    assert track.right == 158.0
    assert track.bottom == 58.0

    clamped = build_patrol_track(
        Rect(left=700.0, top=550.0, width=200.0, height=100.0),
        pet_width=30.0,
        pet_height=30.0,
        screen=Rect(left=0.0, top=0.0, width=800.0, height=600.0),
        gap=8.0,
        margin=4.0,
    )
    assert clamped.right == 766.0
    assert clamped.bottom == 566.0


def test_build_patrol_track_handles_tiny_screen():
    track = build_patrol_track(
        Rect(left=0.0, top=0.0, width=100.0, height=100.0),
        pet_width=30.0,
        pet_height=30.0,
        screen=Rect(left=0.0, top=0.0, width=10.0, height=10.0),
        gap=8.0,
        margin=4.0,
    )
    assert track.right - track.left == pytest.approx(1.0)
    assert track.bottom - track.top == pytest.approx(1.0)
