"""Rate limiting for a camera stream: the newest frame wins, nothing queues.

Frames arrive far faster than decisions are worth asking for. The gate keeps one slot
for the newest frame; a newer frame replaces it (the older one is counted as dropped).
A frame leaves the slot only when fewer than ``max_in_flight`` decisions are running
and at least ``1 / max_rate_hz`` seconds have passed since the last one started.
"""

import threading
import time
from typing import Any, Callable, Optional, Tuple


class FrameGate:
    def __init__(self, max_rate_hz: float, max_in_flight: int = 1, clock: Callable[[], float] = time.monotonic) -> None:
        if not max_rate_hz > 0:
            raise ValueError("max_rate_hz must be above 0, got %r" % (max_rate_hz,))
        if max_in_flight < 1:
            raise ValueError("max_in_flight must be at least 1, got %r" % (max_in_flight,))
        self.interval = 1.0 / float(max_rate_hz)
        self.max_in_flight = int(max_in_flight)
        self._clock = clock
        self._cond = threading.Condition()
        self._slot: Optional[Any] = None
        self._in_flight = 0
        self._last_start: Optional[float] = None
        self._dropped = 0
        self._closed = False

    def offer(self, frame: Any) -> None:
        """Hold ``frame`` for the next decision, replacing any frame still waiting."""
        with self._cond:
            if self._slot is not None:
                self._dropped += 1
            self._slot = frame
            self._cond.notify_all()

    def take(self, timeout: Optional[float] = None) -> Optional[Tuple[Any, int]]:
        """Wait until a frame may start; return it with the frames dropped since the
        last start, or ``None`` on ``timeout`` or once the gate is closed."""
        deadline = None if timeout is None else self._clock() + timeout
        with self._cond:
            while not self._closed:
                now = self._clock()
                wait = self._wait_for(now)
                if wait == 0.0:
                    frame, dropped = self._slot, self._dropped
                    self._slot, self._dropped = None, 0
                    self._in_flight += 1
                    self._last_start = now
                    return frame, dropped
                if deadline is not None:
                    left = deadline - now
                    if left <= 0:
                        return None
                    wait = left if wait is None else min(wait, left)
                self._cond.wait(wait)
            return None

    def done(self) -> None:
        """A decision that started has ended."""
        with self._cond:
            self._in_flight = max(0, self._in_flight - 1)
            self._cond.notify_all()

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    def _wait_for(self, now: float) -> Optional[float]:
        """0.0 when a frame may start now, else the seconds to wait (None: until notified)."""
        if self._slot is None or self._in_flight >= self.max_in_flight:
            return None
        if self._last_start is None:
            return 0.0
        left = self._last_start + self.interval - now
        return 0.0 if left <= 0 else left
