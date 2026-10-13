import threading

import pytest

from decisionnode_ros.gate import FrameGate


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def test_the_newest_frame_wins_and_drops_are_counted():
    gate = FrameGate(max_rate_hz=10, clock=Clock())
    for frame in ("a", "b", "c"):
        gate.offer(frame)
    assert gate.take(timeout=0) == ("c", 2)
    assert gate.take(timeout=0) is None  # nothing waiting


def test_one_in_flight_by_default():
    clock = Clock()
    gate = FrameGate(max_rate_hz=1000, clock=clock)
    gate.offer("a")
    assert gate.take(timeout=0) == ("a", 0)
    gate.offer("b")
    clock.now += 1
    assert gate.take(timeout=0) is None  # "a" still running
    gate.done()
    assert gate.take(timeout=0) == ("b", 0)


def test_the_rate_limit_spaces_the_starts():
    clock = Clock()
    gate = FrameGate(max_rate_hz=2, max_in_flight=4, clock=clock)
    gate.offer("a")
    assert gate.take(timeout=0) == ("a", 0)
    gate.offer("b")
    assert gate.take(timeout=0) is None  # 0.5 s have not passed
    clock.now += 0.5
    assert gate.take(timeout=0) == ("b", 0)


def test_take_waits_for_a_frame_and_close_releases_it():
    gate = FrameGate(max_rate_hz=100)
    got = []
    t = threading.Thread(target=lambda: got.append(gate.take(timeout=2)))
    t.start()
    gate.offer("a")
    t.join(2)
    assert got == [("a", 0)]
    gate.close()
    assert gate.take(timeout=1) is None


@pytest.mark.parametrize("rate, inflight", [(0, 1), (-1, 1), (1, 0)])
def test_bad_limits(rate, inflight):
    with pytest.raises(ValueError):
        FrameGate(max_rate_hz=rate, max_in_flight=inflight)
