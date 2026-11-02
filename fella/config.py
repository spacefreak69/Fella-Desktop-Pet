from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir

APP_NAME = "fella"

BASE_STATES = ("red", "green", "blue", "white", "slate")
PINK_STATE = "pink"
STATES = BASE_STATES + (PINK_STATE,)

DEFAULT_DOOM_PROCESSES = (
    "uzdoom.exe",
    "chocolate-doom.exe",
    "crispy-doom.exe",
    "dsda-doom.exe",
    "prboom-plus.exe",
    "gzdoom.exe",
)

log = logging.getLogger(__name__)


@dataclass
class Config:
    scale: int = 3
    fps: int = 60
    wander_speed_px_s: float = 70.0
    idle_min_s: float = 3.0
    idle_max_s: float = 10.0
    mood_interval_min_s: float = 30.0
    mood_interval_max_s: float = 120.0
    clicks_for_pink: int = 5
    click_window_s: float = 2.0
    pink_duration_s: float = 6.0
    always_on_top: bool = True
    seek_doom: bool = True
    fullscreen_overlay: bool = False
    tracker_poll_interval_s: float = 1.5
    doom_processes: list[str] = field(
        default_factory=lambda: list(DEFAULT_DOOM_PROCESSES)
    )

    @classmethod
    def from_dict(cls, data: Any) -> "Config":
        cfg = cls()
        if not isinstance(data, dict):
            return cfg.normalized()
        for f in fields(cls):
            if f.name not in data:
                continue
            value = data[f.name]
            default = getattr(cfg, f.name)
            try:
                if isinstance(default, bool):
                    value = bool(value)
                elif isinstance(default, int):
                    value = int(value)
                elif isinstance(default, float):
                    value = float(value)
                elif isinstance(default, list):
                    if not isinstance(value, list):
                        value = default
                    else:
                        value = [str(item) for item in value]
            except (TypeError, ValueError):
                value = default
            setattr(cfg, f.name, value)
        return cfg.normalized()

    def normalized(self) -> "Config":
        self.scale = _clamp_int(self.scale, 1, 8, 3)
        self.fps = _clamp_int(self.fps, 15, 144, 60)
        self.wander_speed_px_s = _clamp_float(self.wander_speed_px_s, 5.0, 500.0, 70.0)
        self.idle_min_s = _clamp_float(self.idle_min_s, 0.0, 600.0, 3.0)
        self.idle_max_s = _clamp_float(self.idle_max_s, 0.0, 600.0, 10.0)
        if self.idle_max_s < self.idle_min_s:
            self.idle_min_s, self.idle_max_s = self.idle_max_s, self.idle_min_s
        self.mood_interval_min_s = _clamp_float(
            self.mood_interval_min_s, 1.0, 3600.0, 30.0
        )
        self.mood_interval_max_s = _clamp_float(
            self.mood_interval_max_s, 1.0, 3600.0, 120.0
        )
        if self.mood_interval_max_s < self.mood_interval_min_s:
            self.mood_interval_min_s, self.mood_interval_max_s = (
                self.mood_interval_max_s,
                self.mood_interval_min_s,
            )
        self.clicks_for_pink = _clamp_int(self.clicks_for_pink, 1, 50, 5)
        self.click_window_s = _clamp_float(self.click_window_s, 0.2, 60.0, 2.0)
        self.pink_duration_s = _clamp_float(self.pink_duration_s, 0.5, 300.0, 6.0)
        self.tracker_poll_interval_s = _clamp_float(
            self.tracker_poll_interval_s, 0.25, 30.0, 1.5
        )
        self.always_on_top = bool(self.always_on_top)
        self.seek_doom = bool(self.seek_doom)
        self.fullscreen_overlay = bool(self.fullscreen_overlay)

        seen: set[str] = set()
        processes: list[str] = []
        for name in self.doom_processes:
            name = name.strip()
            key = name.lower()
            if not name or key in seen:
                continue
            seen.add(key)
            processes.append(name)
        self.doom_processes = processes or list(DEFAULT_DOOM_PROCESSES)
        return self


def _clamp_int(value: Any, low: int, high: int, default: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _clamp_float(value: Any, low: float, high: float, default: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default


def config_dir() -> Path:
    return Path(user_config_dir(APP_NAME, appauthor=False))


def config_path() -> Path:
    override = os.environ.get("FELLA_CONFIG")
    if override:
        return Path(override)
    return config_dir() / "config.json"


def load_config(path: Path | None = None) -> Config:
    target = path or config_path()
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        cfg = Config().normalized()
        try:
            save_config(cfg, target)
        except OSError:
            log.warning("Could not write default config to %s", target)
        return cfg
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not read config %s (%s); using defaults", target, exc)
        return Config().normalized()
    return Config.from_dict(raw)


def save_config(config: Config, path: Path | None = None) -> None:
    target = path or config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(asdict(config), indent=2) + "\n"
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=target.parent,
        prefix=target.name + ".",
        suffix=".tmp",
        delete=False,
    )
    tmp_name = handle.name
    try:
        with handle:
            handle.write(payload)
        os.replace(tmp_name, target)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
