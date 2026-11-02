from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from ..config import Config


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent=None) -> None:
        super().__init__(parent)
        self._config = config
        self._result = config
        self.setWindowTitle("fella settings")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setMinimumWidth(420)

        self.scale = QSpinBox()
        self.scale.setRange(1, 8)
        self.scale.setSuffix("x")
        self.scale.setValue(config.scale)

        self.fps = QSpinBox()
        self.fps.setRange(15, 144)
        self.fps.setSuffix(" fps")
        self.fps.setValue(config.fps)

        self.always_on_top = QCheckBox("Always on top")
        self.always_on_top.setChecked(config.always_on_top)

        self.speed = _seconds_spin(5.0, 500.0)
        self.speed.setSuffix(" px/s")
        self.speed.setValue(config.wander_speed_px_s)

        self.idle_min = _seconds_spin(0.0, 600.0)
        self.idle_min.setValue(config.idle_min_s)

        self.idle_max = _seconds_spin(0.0, 600.0)
        self.idle_max.setValue(config.idle_max_s)

        self.mood_min = _seconds_spin(1.0, 3600.0)
        self.mood_min.setValue(config.mood_interval_min_s)

        self.mood_max = _seconds_spin(1.0, 3600.0)
        self.mood_max.setValue(config.mood_interval_max_s)

        self.clicks_for_pink = QSpinBox()
        self.clicks_for_pink.setRange(1, 50)
        self.clicks_for_pink.setValue(config.clicks_for_pink)

        self.click_window = _seconds_spin(0.2, 60.0)
        self.click_window.setValue(config.click_window_s)

        self.pink_duration = _seconds_spin(0.5, 300.0)
        self.pink_duration.setValue(config.pink_duration_s)

        self.seek_doom = QCheckBox("Walk around Doom source port windows")
        self.seek_doom.setChecked(config.seek_doom)

        self.fullscreen_overlay = QCheckBox(
            "Overlay over fullscreen apps (click-through)"
        )
        self.fullscreen_overlay.setChecked(config.fullscreen_overlay)
        self.fullscreen_overlay.setToolTip(
            "Roam inside any foreground fullscreen app without taking input. "
            "Works with borderless fullscreen; exclusive fullscreen is not supported."
        )

        self.poll_interval = _seconds_spin(0.25, 30.0)
        self.poll_interval.setValue(config.tracker_poll_interval_s)

        self.doom_processes = QPlainTextEdit()
        self.doom_processes.setPlainText("\n".join(config.doom_processes))
        self.doom_processes.setPlaceholderText("One executable per line")
        self.doom_processes.setFixedHeight(110)

        appearance = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance)
        appearance_form.addRow("Sprite scale", self.scale)
        appearance_form.addRow("Animation rate", self.fps)
        appearance_form.addRow(self.always_on_top)

        wandering = QGroupBox("Wandering")
        wandering_form = QFormLayout(wandering)
        wandering_form.addRow("Speed", self.speed)
        wandering_form.addRow("Idle minimum", self.idle_min)
        wandering_form.addRow("Idle maximum", self.idle_max)
        wandering_form.addRow("Mood interval minimum", self.mood_min)
        wandering_form.addRow("Mood interval maximum", self.mood_max)

        interaction = QGroupBox("Interaction")
        interaction_form = QFormLayout(interaction)
        interaction_form.addRow("Clicks for pink", self.clicks_for_pink)
        interaction_form.addRow("Click window", self.click_window)
        interaction_form.addRow("Pink duration", self.pink_duration)

        doom = QGroupBox("Doom source ports")
        doom_layout = QVBoxLayout(doom)
        doom_form = QFormLayout()
        doom_form.addRow(self.seek_doom)
        doom_form.addRow("Re-scan interval", self.poll_interval)
        doom_layout.addLayout(doom_form)
        doom_layout.addWidget(self.doom_processes)

        fullscreen = QGroupBox("Fullscreen")
        fullscreen_layout = QVBoxLayout(fullscreen)
        fullscreen_layout.addWidget(self.fullscreen_overlay)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(appearance)
        layout.addWidget(wandering)
        layout.addWidget(interaction)
        layout.addWidget(doom)
        layout.addWidget(fullscreen)
        layout.addWidget(buttons)

    def result_config(self) -> Config:
        return self._result

    def accept(self) -> None:
        doom_names = [
            line.strip()
            for line in self.doom_processes.toPlainText().splitlines()
            if line.strip()
        ]
        self._result = replace(
            self._config,
            scale=self.scale.value(),
            fps=self.fps.value(),
            wander_speed_px_s=self.speed.value(),
            idle_min_s=self.idle_min.value(),
            idle_max_s=self.idle_max.value(),
            mood_interval_min_s=self.mood_min.value(),
            mood_interval_max_s=self.mood_max.value(),
            clicks_for_pink=self.clicks_for_pink.value(),
            click_window_s=self.click_window.value(),
            pink_duration_s=self.pink_duration.value(),
            always_on_top=self.always_on_top.isChecked(),
            seek_doom=self.seek_doom.isChecked(),
            fullscreen_overlay=self.fullscreen_overlay.isChecked(),
            tracker_poll_interval_s=self.poll_interval.value(),
            doom_processes=doom_names,
        ).normalized()
        super().accept()


def _seconds_spin(low: float, high: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(low, high)
    spin.setDecimals(2)
    spin.setSingleStep(0.5)
    spin.setSuffix(" s")
    return spin
