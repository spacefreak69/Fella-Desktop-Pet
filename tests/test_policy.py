from fella.behavior.policy import (
    MODE_HIDE,
    MODE_OVERLAY,
    MODE_PATROL,
    MODE_ROAM,
    decide_mode,
)
from fella.config import Config
from fella.tracking.base import TrackedWindow


def _window(**overrides) -> TrackedWindow:
    values = {
        "handle": 1,
        "title": "game",
        "process": "gzdoom.exe",
        "x": 0,
        "y": 0,
        "width": 800,
        "height": 600,
        "pid": 1234,
    }
    values.update(overrides)
    return TrackedWindow(**values)


def test_no_foreground_roams():
    assert decide_mode(Config(), None, 99, False) == MODE_ROAM


def test_own_process_is_ignored():
    config = Config(fullscreen_overlay=True)
    foreground = _window(fullscreen=True, pid=99)
    assert decide_mode(config, foreground, 99, False) == MODE_ROAM


def test_overlay_any_fullscreen_app_when_enabled():
    config = Config(fullscreen_overlay=True, seek_doom=False)
    foreground = _window(process="firefox.exe", fullscreen=True)
    assert decide_mode(config, foreground, 99, False) == MODE_OVERLAY


def test_fullscreen_doom_hides_without_overlay():
    config = Config(fullscreen_overlay=False, seek_doom=True)
    foreground = _window(fullscreen=True)
    assert decide_mode(config, foreground, 99, True) == MODE_HIDE


def test_windowed_doom_patrols_even_with_overlay_enabled():
    config = Config(fullscreen_overlay=True, seek_doom=True)
    foreground = _window(fullscreen=False)
    assert decide_mode(config, foreground, 99, True) == MODE_PATROL


def test_seek_disabled_roams_for_windowed_doom():
    config = Config(fullscreen_overlay=False, seek_doom=False)
    foreground = _window(fullscreen=False)
    assert decide_mode(config, foreground, 99, True) == MODE_ROAM


def test_minimized_foreground_roams():
    config = Config(fullscreen_overlay=True, seek_doom=True)
    foreground = _window(fullscreen=True, minimized=True)
    assert decide_mode(config, foreground, 99, True) == MODE_ROAM
