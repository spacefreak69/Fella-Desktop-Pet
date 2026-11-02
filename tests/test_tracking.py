from fella.tracking.base import (
    NullTracker,
    TrackedWindow,
    matches_process,
    process_stem,
)


def test_process_stem_handles_paths_and_case():
    assert process_stem("C:\\Games\\UZDoom.EXE") == "uzdoom"
    assert process_stem("/usr/bin/chocolate-doom") == "chocolate-doom"
    assert process_stem("gzdoom.exe") == "gzdoom"
    assert process_stem("") == ""


def test_matches_process_ignores_exe_suffix_and_case():
    candidates = ["uzdoom.exe", "chocolate-doom"]
    assert matches_process("UZDoom.exe", candidates)
    assert matches_process("chocolate-doom.exe", candidates)
    assert not matches_process("firefox.exe", candidates)
    assert not matches_process("", candidates)


def test_window_center():
    window = TrackedWindow(
        handle=1, title="t", process="gzdoom.exe", x=10, y=20, width=100, height=50
    )
    assert window.center == (60.0, 45.0)
    assert window.pid is None


def test_null_tracker_has_no_foreground_window():
    tracker = NullTracker()
    assert tracker.get_windows(["gzdoom.exe"]) == []
    assert tracker.get_foreground_window() is None
    assert tracker.close() is None
