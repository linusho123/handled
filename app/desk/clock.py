"""The desk's clock: real at the demo, virtual in test mode.

Times are naive local wall time (the laptop's zone, America/Los_Angeles at the
event); "nine in the morning the day before" (D20) is read on this clock. The
virtual clock moves only when told (POST /test/advance), so no scenario waits
real time. In test mode the app's event loop runs on it too (VirtualTimeLoop):
every timer the app could schedule falls due when the clock is advanced.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any

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


class VirtualTimeLoop(asyncio.SelectorEventLoop):
    """Test mode's event loop (head-1): its time is real time plus every second the
    virtual clock has been advanced, so a timer anything in the app schedules
    (call_later, call_at, asyncio.sleep) falls due on POST /test/advance exactly as
    it would after that much real time. A timer that taps Confirm therefore fires
    inside the walk-away outline's jump, and the outline sees it (D6)."""

    # Rounds of the loop with nothing due and nothing ready before an advance answers.
    _QUIET_ROUNDS = 3
    _MAX_ROUNDS = 10_000

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._skipped = 0.0

    def time(self) -> float:
        return super().time() + self._skipped

    async def advance(self, seconds: float) -> None:
        """Move the loop's time forward and yield until every callback that fell due
        has run, and the tasks those callbacks started have taken their steps."""
        if not seconds >= 0:
            raise ValueError("the clock never runs backwards")
        self._skipped += seconds
        await self.settle()

    def _busy(self) -> bool:
        now = self.time()
        due = any(not h.cancelled() and h.when() <= now for h in self._scheduled)  # type: ignore[attr-defined]
        return due or bool(self._ready)  # type: ignore[attr-defined]

    async def settle(self) -> None:
        quiet = 0
        for _ in range(self._MAX_ROUNDS):
            await asyncio.sleep(0)
            quiet = 0 if self._busy() else quiet + 1
            if quiet >= self._QUIET_ROUNDS:
                return
