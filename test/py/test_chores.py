"""risk-1: a Playwright error inside a chore's step (a field that never appears, a
navigation that fails) is a failed step: the card names the step, no control is left,
the browser stays where it was, and the wait for it is bounded, never Playwright's 30 s."""

import asyncio
import time

from app.desk import Desk
from app.eye import Identification
from app.hands import Hands
from app.hands.chores import BaseChore

STEP = "Could not fill the card on file"


class NoField(BaseChore):
    """A chore whose one step fills a field the page never shows."""

    begin_step = STEP

    async def _begin(self) -> None:
        self.desk.card.controls = ["Pay", "Contest"]
        self.page = await self.hands.new_tab()
        await self.page.set_content("<title>Pay</title><form><input id='amount'></form>")
        await self.page.fill("#card_name", "Pat Driver")


def test_risk_1_a_field_that_never_appears_is_a_named_failed_step_within_the_bound():
    async def main():
        hands = Hands(headless=True, step_timeout_ms=1000)
        await hands.start()
        try:
            desk = Desk()
            chore = NoField(hands, None, desk, None, Identification(kind="ticket", fields={}))
            started = time.monotonic()
            await chore.begin()  # raises nothing: the failure is on the card
            elapsed = time.monotonic() - started
            assert elapsed < 5, elapsed
            assert desk.card.failed_step == STEP
            assert desk.card.controls == [] and desk.card.question is None
            assert chore.stopped
            assert len(hands.pages) == 1 and desk.card.link == hands.pages[0].url
            assert await hands.pages[0].title() == "Pay"
        finally:
            await hands.stop()

    asyncio.run(main())


def test_risk_1_the_hands_bound_every_step_by_default():
    assert Hands().step_timeout_ms <= 15_000
