from fella.behavior.clicks import ClickCounter


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_fires_on_threshold_and_clears():
    clock = FakeClock()
    counter = ClickCounter(threshold=3, window_s=2.0, clock=clock)
    assert counter.register_click() is False
    assert counter.register_click() is False
    assert counter.count == 2
    assert counter.register_click() is True
    assert counter.count == 0


def test_old_clicks_expire():
    clock = FakeClock()
    counter = ClickCounter(threshold=2, window_s=2.0, clock=clock)
    assert counter.register_click() is False
    clock.now = 5.0
    assert counter.register_click() is False
    assert counter.count == 1


def test_clicks_within_window_accumulate():
    clock = FakeClock()
    counter = ClickCounter(threshold=2, window_s=2.0, clock=clock)
    assert counter.register_click() is False
    clock.now = 1.9
    assert counter.register_click() is True


def test_reset_and_configure():
    clock = FakeClock()
    counter = ClickCounter(threshold=5, window_s=2.0, clock=clock)
    counter.register_click()
    counter.reset()
    assert counter.count == 0
    counter.configure(threshold=1, window_s=2.0)
    assert counter.register_click() is True
