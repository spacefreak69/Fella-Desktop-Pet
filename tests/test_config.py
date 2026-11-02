import json

from fella.config import (
    DEFAULT_DOOM_PROCESSES,
    Config,
    load_config,
    save_config,
)


def test_defaults_are_normalized():
    config = Config().normalized()
    assert config.scale == 3
    assert config.fps == 60
    assert config.doom_processes == list(DEFAULT_DOOM_PROCESSES)


def test_from_dict_clamps_and_ignores_unknown():
    config = Config.from_dict(
        {
            "scale": 99,
            "fps": 1,
            "wander_speed_px_s": -10,
            "idle_min_s": 20,
            "idle_max_s": 5,
            "mood_interval_min_s": 100,
            "mood_interval_max_s": 10,
            "clicks_for_pink": 0,
            "pink_duration_s": "nope",
            "unknown_key": "ignored",
        }
    )
    assert config.scale == 8
    assert config.fps == 15
    assert config.wander_speed_px_s == 5.0
    assert config.idle_min_s == 5.0
    assert config.idle_max_s == 20.0
    assert config.mood_interval_min_s == 10.0
    assert config.mood_interval_max_s == 100.0
    assert config.clicks_for_pink == 1
    assert config.pink_duration_s == 6.0


def test_fullscreen_overlay_defaults_off_and_parses():
    assert Config().normalized().fullscreen_overlay is False
    assert Config.from_dict({"fullscreen_overlay": True}).fullscreen_overlay is True


def test_legacy_hide_in_fullscreen_key_is_ignored():
    config = Config.from_dict({"hide_in_fullscreen": False})
    assert config.fullscreen_overlay is False


def test_doom_processes_are_cleaned():
    config = Config.from_dict(
        {
            "doom_processes": [
                " gzdoom.exe ",
                "GZDoom.exe",
                "",
                "chocolate-doom.exe",
            ]
        }
    )
    assert config.doom_processes == ["gzdoom.exe", "chocolate-doom.exe"]


def test_empty_doom_processes_fall_back_to_defaults():
    config = Config.from_dict({"doom_processes": []})
    assert config.doom_processes == list(DEFAULT_DOOM_PROCESSES)


def test_non_dict_input_returns_defaults():
    assert Config.from_dict(None) == Config()


def test_roundtrip(tmp_path):
    path = tmp_path / "nested" / "config.json"
    config = Config(scale=4, fps=30, doom_processes=["gzdoom.exe"]).normalized()
    save_config(config, path)
    assert json.loads(path.read_text(encoding="utf-8"))["scale"] == 4
    assert load_config(path) == config


def test_missing_file_creates_default(tmp_path):
    path = tmp_path / "config.json"
    config = load_config(path)
    assert path.is_file()
    assert config == Config()


def test_corrupt_file_uses_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_config(path) == Config()
