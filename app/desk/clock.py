"""The desk's clock: real at the demo, virtual in test mode.

Times are naive local wall time (the laptop's zone, America/Los_Angeles at the
event); "nine in the morning the day before" (D20) is read on this clock. The
virtual clock moves only when told (POST /test/advance), so no scenario waits
real time.
"""

from __future__ import annotations

from datetime import datetime, timedelta

LOCAL_ZONE = "America/Los_Angeles"
# Where every test scenario's day begins unless /test/reset names another start.
VIRTUAL_START = datetime(2026, 10, 17, 0, 0, 0)


class Clock:
    def now(self) -> datetime:
        raise NotImplementedError


class RealClock(Clock):
    def now(self) -> datetime:
        return datetime.now().replace(microsecond=0)


class VirtualClock(Clock):
    def __init__(self, start: datetime = VIRTUAL_START) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def reset(self, start: datetime = VIRTUAL_START) -> datetime:
        self._now = start
        return self._now

    def advance(self, seconds: float) -> datetime:
        if seconds < 0:
            raise ValueError("the clock never runs backwards")
        self._now = self._now + timedelta(seconds=seconds)
        return self._now
