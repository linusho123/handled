"""The chores the hands carry out in the visible browser.

TicketChore (D9-D13): the city's pay-or-contest page with the citation and the
plate filled, Pay or Contest on the card, the payment form with the card on
file or the contest form with the letter, then the Confirm gate. BillChore and
ProductChore here only open the page their chore starts on (identify.feature,
D4); the bill chore is P4 and the product chore P3.

A step that fails raises StepFailed: the card names the step, the browser stays
on the page it reached, and nothing is submitted (D10).
"""

from __future__ import annotations

import re
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from app.desk.deadlines import ticket_deadline
from app.desk.state import Desk
from app.desk.wallet import CARD_ON_FILE
from app.eye import Identification
from app.hands import Hands
from app.hands.sitemap import CityPortal, SiteMap


class StepFailed(Exception):
    def __init__(self, step: str, page_url: str | None = None) -> None:
        super().__init__(step)
        self.step = step
        self.page_url = page_url


class BaseChore:
    def __init__(self, hands: Hands, sites: SiteMap, desk: Desk, eye: Any, ident: Identification) -> None:
        self.hands = hands
        self.sites = sites
        self.desk = desk
        self.eye = eye
        self.ident = ident
        self.fields = ident.fields
        self.page: Page | None = None
        self.stopped = False

    async def begin(self) -> None:
        await self._run(self._begin)

    async def tap(self, control: str) -> bool:
        return False

    async def say(self, text: str) -> bool:
        return False

    async def _begin(self) -> None:
        raise NotImplementedError

    async def _run(self, step: Any, *args: Any) -> None:
        """Run a step; a failure stops the chore where it stands."""
        try:
            await step(*args)
        except StepFailed as failed:
            self.stopped = True
            self.desk.card.controls = []
            self.desk.card.question = None
            self.desk.card.failed_step = failed.step
        finally:
            if self.page is not None:
                self.desk.card.link = self.page.url

    async def _open(self, url: str, step: str) -> Page:
        """Navigate the chore's tab; a page that does not answer is a failed step, and the tab stays."""
        if self.page is None:
            self.page = await self.hands.new_tab()
        try:
            response = await self.page.goto(url)
        except PlaywrightError as err:
            raise StepFailed(step) from err
        if response is None or response.status >= 500 or not (await response.body()).strip():
            raise StepFailed(step)
        return self.page


class TicketChore(BaseChore):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.portal: CityPortal | None = None
        self.awaiting_reason = False

    @property
    def citation(self) -> str:
        return str(self.fields["citation"])

    async def _begin(self) -> None:
        card = self.desk.card
        card.deadline, card.deadline_note = ticket_deadline(self.fields)
        city = self.fields.get("city")
        self.portal = self.sites.city(city)
        if self.portal is None:
            # D27: other cities are best effort; none is known yet, so the chore stops here.
            raise StepFailed(f"No pay-or-contest page is known for {city}")
        portal = self.portal
        page = await self._open(portal.lookup_url, f"Could not reach the {portal.city} citation page")
        await self._no_login(page)
        await page.fill(portal.citation_field, self.citation)
        await page.fill(portal.plate_field, str(self.fields["plate"]))
        async with page.expect_navigation():
            await page.click(portal.lookup_button)
        await self._no_login(page)
        if await page.locator(portal.found).count() == 0:
            raise StepFailed(f"Citation {self.citation} was not found")
        card.controls = ["Pay", "Contest"]

    async def _no_login(self, page: Page) -> None:
        assert self.portal is not None
        if await page.locator(self.portal.login_wall).count() > 0:
            raise StepFailed("The city's page asks for a login")  # D26: Handled holds no passwords

    async def tap(self, control: str) -> bool:
        if self.stopped or control not in self.desk.card.controls:
            return False
        if control == "Pay":
            await self._run(self._pay)
            return True
        if control == "Contest":
            await self._run(self._contest)
            return True
        return False

    async def say(self, text: str) -> bool:
        if self.stopped:
            return False
        if self.awaiting_reason:
            await self._run(self._letter, text)
            return True
        words = text.strip()
        if "Pay" in self.desk.card.controls and re.match(r"^pay\b", words, re.IGNORECASE):
            await self._run(self._pay)
            return True
        m = re.match(r"^contest\b[\s,.:;-]*(.*)$", words, re.IGNORECASE | re.DOTALL)
        if "Contest" in self.desk.card.controls and m:
            await self._run(self._contest)
            if m.group(1).strip() and self.awaiting_reason:
                await self._run(self._letter, m.group(1))
            return True
        return False

    async def _follow(self, link: str) -> Page:
        assert self.page is not None
        page = self.page
        async with page.expect_navigation():
            await page.click(link)
        await self._no_login(page)
        return page

    async def _pay(self) -> None:
        """D11: the payment page, the card on file filled, paused before submit."""
        portal = self.portal
        assert portal is not None
        self.desk.card.controls = []
        page = await self._follow(portal.pay_link)
        await page.fill(portal.card_name, CARD_ON_FILE.name)
        await page.fill(portal.card_number, CARD_ON_FILE.number)
        await page.fill(portal.card_expiry, CARD_ON_FILE.expiry)
        await page.fill(portal.card_cvc, CARD_ON_FILE.cvc)
        self.desk.card.link = page.url
        self.desk.pause_for_confirm(lambda: self._run(self._submit, portal.pay, f"Paid citation {self.citation}", "The city's page did not take the payment"))

    async def _contest(self) -> None:
        """D12: the contest form, and the card asks for the reason."""
        portal = self.portal
        assert portal is not None
        self.desk.card.controls = []
        await self._follow(portal.contest_link)
        self.awaiting_reason = True
        self.desk.card.question = "Why are you contesting it?"

    async def _letter(self, reason: str) -> None:
        portal = self.portal
        assert portal is not None and self.page is not None
        letter = self.eye.write_letter(self.fields, reason)
        self.awaiting_reason = False
        self.desk.card.question = None
        self.desk.card.letter = letter
        await self.page.fill(portal.letter, letter)
        self.desk.pause_for_confirm(lambda: self._run(self._submit, portal.contest, f"Contest filed for citation {self.citation}", "The city's page did not take the contest"))

    async def _submit(self, button: Any, done: str, refused: str) -> None:
        """Runs only from Desk.confirm (the Confirm gate); the city's receipt is what says it is done."""
        assert self.portal is not None and self.page is not None
        await self.hands.submit_final(self.page, button, self.desk)
        if await self.page.locator(self.portal.receipt).count() == 0:
            raise StepFailed(refused)
        self.desk.card.done = done


class BillChore(BaseChore):
    """P1 opens the biller's payment page (D4); filling and paying it is P4."""

    async def _begin(self) -> None:
        self.desk.card.deadline = self.fields.get("due")
        biller = self.sites.biller(self.fields.get("biller"))
        if biller is None:
            raise StepFailed(f"No payment page is known for {self.fields.get('biller')}")
        await self._open(biller.pay_url, f"Could not reach the {biller.name} payment page")


class ProductChore(BaseChore):
    """P1 opens the first store's search for the product (D4); the three tabs and the ranking are P3."""

    async def _begin(self) -> None:
        store = self.sites.stores[0]
        query = f"{self.fields['name']} {self.fields['size']}"
        await self._open(store.search(query), f"Could not reach {store.name}")


CHORES = {"ticket": TicketChore, "bill": BillChore, "product": ProductChore}


def chore_for(hands: Hands, sites: SiteMap, eye: Any):
    def make(desk: Desk, ident: Identification) -> BaseChore:
        return CHORES[ident.kind](hands, sites, desk, eye, ident)

    return make
