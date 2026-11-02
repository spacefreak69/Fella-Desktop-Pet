import random

from fella.behavior.mood import pick_mood
from fella.config import BASE_STATES


def test_pick_mood_never_repeats_current():
    rng = random.Random(1234)
    for _ in range(200):
        for current in BASE_STATES:
            choice = pick_mood(current, rng)
            assert choice in BASE_STATES
            assert choice != current


def test_pick_mood_falls_back_when_single_state(monkeypatch):
    monkeypatch.setattr("fella.behavior.mood.BASE_STATES", ("red",))
    assert pick_mood("red", random.Random(0)) == "red"
