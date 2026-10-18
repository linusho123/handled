"""The chores the hands carry out in the visible browser.

TicketChore (D9-D13): the city's pay-or-contest page with the citation and the
plate filled, Pay or Contest on the card, the payment form with the card on
file or the contest form with the letter, then the Confirm gate. BillChore
(D14, D15): the biller's payment page with the account number, the amount and the
card on file filled, then the Confirm gate; with no payment page found, a page that
does not answer or a login wall, nothing is paid and the card shows "call to pay"
with the phone number the bill itself prints. ProductChore (D16-D18): three store
tabs, the prices read from each product page, the ranked card with Buy on the
cheapest, Buy to checkout, then the Confirm gate.

Every chore end is reported (D19): a step that completes after Confirm, a pause
at Confirm (Desk.pause_for_confirm) and a failed step each call Desk.report once,
which puts what was done on the card and sends the one text.

A step that fails raises StepFailed: the card names the step, the browser stays
on the page it reached, and nothing is submitted (D10). A Playwright error inside
a step (a field that never appears, a navigation that fails) is that step
failing, under the step's own name (risk-1).
"""

from __future__ import annotations

import sys

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page

from app.desk.deadlines import deadline_for
from app.desk.state import Desk
from app.desk.wallet import CARD_ON_FILE, SHIP_TO
from app.eye import Identification
from app.hands import Hands
from app.hands.sitemap import Biller, CityPortal, SiteMap, Store


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

    @property
    def begin_step(self) -> str:
        """The name the card shows when the chore's first step fails."""
        return "Could not open the page"

    async def begin(self) -> None:
        await self._run(self.begin_step, self._begin)

    async def tap(self, control: str) -> bool:
        return False

    async def say(self, text: str) -> bool:
        return False

    async def _begin(self) -> None:
        raise NotImplementedError

    async def _run(self, name: str, step: Any, *args: Any) -> None:
        """Run a step; a failure stops the chore where it stands. `name` is what the
        card shows when the browser itself fails inside the step."""
        try:
            try:
                await step(*args)
            except PlaywrightError as err:
                raise StepFailed(name, self.page.url if self.page is not None else None) from err
        except StepFailed as failed:
            # The operator reads why on stderr; the card shows only the step's name (D10, D15).
            cause = failed.__cause__
            print(f"handled hands: step failed: {failed.step}" + (f" ({type(cause).__name__}: {str(cause).splitlines()[0][:160]})" if cause else ""), file=sys.stderr, flush=True)
            self.stopped = True
            self.desk.card.controls = []
            self.desk.card.question = None
            self.desk.card.failed_step = failed.step
            if self.page is not None:
                self.desk.card.link = self.page.url
            self.desk.report(self._stopped_at(failed.step))  # D19: a failed step is a chore end
        finally:
            if self.page is not None:
                self.desk.card.link = self.page.url

    def _stopped_at(self, step: str) -> str:
        """What the card and the text say was done when the chore stopped at `step`."""
        return step

    async def _open(self, url: str, step: str) -> Page:
        """Navigate the chore's tab; a page that does not answer is a failed step, and the tab stays."""
        if self.page is None:
            self.page = await self.hands.new_tab()
        try:
            response = await self.page.goto(url)
        except PlaywrightError as err:
            raise StepFailed(step) from err
        await self._answered(response, step)
        return self.page

    async def _answered(self, response: Any, step: str) -> None:
        """A navigation that brought back nothing (no response, a 5xx, an empty page) is a failed step."""
        if response is None or response.status >= 500 or not (await response.body()).strip():
            raise StepFailed(step, self.page.url if self.page is not None else None)


# The name the card shows when the browser fails inside each ticket step (risk-1).
PAY_STEP = "Could not fill the card on file on the city's payment page"
CONTEST_STEP = "Could not open the city's contest form"
LETTER_STEP = "Could not paste the letter into the city's contest form"


class TicketChore(BaseChore):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.portal: CityPortal | None = None
        self.awaiting_reason = False

    @property
    def citation(self) -> str:
        return str(self.fields["citation"])

    @property
    def begin_step(self) -> str:
        return f"Could not look up citation {self.fields.get('citation')}"

    async def _begin(self) -> None:
        card = self.desk.card
        card.deadline, card.deadline_note = deadline_for("ticket", self.fields)
        city = self.fields.get("city")
        self.portal = self.sites.city(city)
        if self.portal is None:
            # D27: other cities are best effort; none is known yet, so the chore stops here.
            raise StepFailed(f"No pay-or-contest page is known for {city}")
        portal = self.portal
        page = await self._open(portal.lookup_url, f"Could not reach the {portal.city} citation page")
        await self._no_login(page)
        if portal.lookup_choice:
            await page.check(portal.lookup_choice)
        await page.fill(portal.citation_field, self.citation)
        if portal.plate_field:  # the real Los Angeles page has no plate box
            await page.fill(portal.plate_field, str(self.fields["plate"]))
        if portal.captcha_field and await page.locator(portal.captcha_field).count() > 0:
            # D36: the agent never solves a CAPTCHA. The card says so, and the chore waits, with no
            # time-out, for the user to type it in the visible browser and press the page's own button.
            card.notice = "Type the CAPTCHA in the browser and press Submit; I will carry on from there"
            async with page.expect_navigation(timeout=0):
                pass
            card.notice = None
        else:
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
            await self._run(PAY_STEP, self._pay)
            return True
        if control == "Contest":
            await self._run(CONTEST_STEP, self._contest)
            return True
        return False

    async def say(self, text: str) -> bool:
        if self.stopped:
            return False
        if self.awaiting_reason:
            await self._run(LETTER_STEP, self._letter, text)
            return True
        words = text.strip()
        if "Pay" in self.desk.card.controls and re.match(r"^pay\b", words, re.IGNORECASE):
            await self._run(PAY_STEP, self._pay)
            return True
        m = re.match(r"^contest\b[\s,.:;-]*(.*)$", words, re.IGNORECASE | re.DOTALL)
        if "Contest" in self.desk.card.controls and m:
            await self._run(CONTEST_STEP, self._contest)
            if m.group(1).strip() and self.awaiting_reason:
                await self._run(LETTER_STEP, self._letter, m.group(1))
            return True
        return False

    async def _follow(self, link: str, step: str) -> Page:
        """Follow a link on the city's page; a page that does not answer is a failed step, and the tab stays."""
        assert self.page is not None
        page = self.page
        async with page.expect_navigation() as navigation:
            await page.click(link)
        await self._answered(await navigation.value, step)
        await self._no_login(page)
        return page

    async def _pay(self) -> None:
        """D11: the payment page, the card on file filled, paused before submit."""
        portal = self.portal
        assert portal is not None
        self.desk.card.controls = []
        page = await self._follow(portal.pay_link, "Could not reach the city's payment page")
        await page.fill(portal.card_name, CARD_ON_FILE.name)
        await page.fill(portal.card_number, CARD_ON_FILE.number)
        await page.fill(portal.card_expiry, CARD_ON_FILE.expiry)
        await page.fill(portal.card_cvc, CARD_ON_FILE.cvc)
        self.desk.card.link = page.url
        refused = "The city's page did not take the payment"
        self.desk.pause_for_confirm(
            lambda: self._run(refused, self._submit, portal.pay, f"Paid citation {self.citation}", refused),
            f"Ready to pay citation {self.citation}, waiting for you",
        )

    async def _contest(self) -> None:
        """D12: the contest form, and the card asks for the reason."""
        portal = self.portal
        assert portal is not None
        self.desk.card.controls = []
        await self._follow(portal.contest_link, "Could not reach the city's contest form")
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
        refused = "The city's page did not take the contest"
        self.desk.card.link = self.page.url
        self.desk.pause_for_confirm(
            lambda: self._run(refused, self._submit, portal.contest, f"Contest filed for citation {self.citation}", refused),
            f"Ready to contest citation {self.citation}, waiting for you",
        )

    async def _submit(self, button: Any, done: str, refused: str) -> None:
        """Runs only from Desk.confirm (the Confirm gate); the city's receipt is what says it is done."""
        assert self.portal is not None and self.page is not None
        await self.hands.submit_final(self.page, button, self.desk)
        if await self.page.locator(self.portal.receipt).count() == 0:
            raise StepFailed(refused)
        self.desk.card.link = self.page.url
        self.desk.report(done)  # D19: completed after Confirm


CALL_TO_PAY = "call to pay"


def amount_shown(amount: Any) -> str:
    """148.22 → "$148.22", the amount as the card and the texts say it."""
    return f"${Decimal(str(amount)).quantize(Decimal('0.01'))}"


class BillChore(BaseChore):
    """D14: the biller's payment page in the visible browser (the SiteMap's; with none
    there, the biller's own site search for it), the account number, the amount and the
    card on file filled, then the pause before paying (D7). D15, D26: no payment page
    found, a page that does not answer or a login wall stops the chore with nothing paid,
    the browser left where it stood, and the card shows "call to pay" with the phone
    number printed on the bill: the identification's own field, never a page's."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.biller: Biller | None = None
        self.past_gate = False  # set once Confirm runs Pay now; nothing after it is "call to pay"

    @property
    def name(self) -> str:
        return str(self.fields.get("biller") or "the biller")

    @property
    def amount(self) -> str:
        return amount_shown(self.fields["amount"])

    @property
    def begin_step(self) -> str:
        return f"Could not fill the {self.name} payment page"

    def _stopped_at(self, step: str) -> str:
        # D15: "call to pay" only for a stop before the gate. Once Pay now has been pressed
        # the chore cannot know nothing was paid: the step and the browser link alone (head-1).
        phone = self.fields.get("phone")  # as the bill prints it (the eye's read)
        if not phone or self.past_gate:
            return step
        self.desk.card.call_to_pay = str(phone)
        return f"{step}: {CALL_TO_PAY} {phone}"

    async def _begin(self) -> None:
        self.desk.card.deadline, self.desk.card.deadline_note = deadline_for("bill", self.fields)
        self.biller = self.sites.biller(self.fields.get("biller"))
        if self.biller is None:
            # A biller the SiteMap does not know. Its finder (Browser Use) is deferred (P4: its
            # cassette could not be recorded), so the chore stops here with "call to pay".
            raise StepFailed(f"No payment page is known for {self.name}")
        biller = self.biller
        unreachable = f"Could not reach the {biller.name} payment page"
        page = await self._open(biller.pay_url, unreachable)
        await self._no_login(page)
        if not await self._is_payment_page(page):
            page = await self._search(biller, unreachable)
        await page.fill(biller.account, str(self.fields["account"]))
        await page.fill(biller.amount, str(self.fields["amount"]))
        await page.fill(biller.card_name, CARD_ON_FILE.name)
        await page.fill(biller.card_number, CARD_ON_FILE.number)
        await page.fill(biller.card_expiry, CARD_ON_FILE.expiry)
        await page.fill(biller.card_cvc, CARD_ON_FILE.cvc)
        self.desk.card.link = page.url
        refused = f"The {biller.name} page did not take the payment"
        self.desk.pause_for_confirm(
            lambda: self._run(refused, self._pay, refused),
            f"Ready to pay {biller.name} {self.amount}, waiting for you",
        )

    async def _is_payment_page(self, page: Page) -> bool:
        assert self.biller is not None
        return await page.locator(self.biller.account).count() > 0

    async def _no_login(self, page: Page) -> None:
        assert self.biller is not None
        if await page.locator(self.biller.login_wall).count() > 0:
            raise StepFailed(f"The {self.biller.name} page asks for a login", page.url)  # D26: no passwords

    async def _search(self, biller: Biller, unreachable: str) -> Page:
        """No payment page where the SiteMap put it: the biller's own search, and the first
        result whose words say pay. None found is the stop, on the results it tried (D15)."""
        not_found = f"No payment page for {biller.name} was found"
        url = biller.search(f"pay {biller.name} bill")
        if url is None:
            raise StepFailed(not_found, self.page.url if self.page is not None else None)
        page = await self._open(url, unreachable)
        await self._no_login(page)
        results = page.locator(biller.search_result)
        for i in range(await results.count()):
            hit = results.nth(i)
            if re.search(r"\bpay\b", await hit.inner_text(), re.IGNORECASE):
                async with page.expect_navigation() as navigation:
                    await hit.click()
                await self._answered(await navigation.value, unreachable)
                await self._no_login(page)
                if await self._is_payment_page(page):
                    return page
                break
        raise StepFailed(not_found, page.url)

    async def _pay(self, refused: str) -> None:
        """Runs only from Desk.confirm (the Confirm gate); the biller's receipt is what says it is paid."""
        assert self.biller is not None and self.page is not None
        self.past_gate = True
        await self.hands.submit_final(self.page, self.biller.pay, self.desk)
        if await self.page.locator(self.biller.receipt).count() == 0:
            raise StepFailed(refused, self.page.url)
        self.desk.card.link = self.page.url
        self.desk.report(f"Paid {self.biller.name} {self.amount}")  # D19: completed after Confirm


@dataclass(frozen=True)
class Offer:
    """One store's price for the product, as its product page showed it."""

    store: Store
    price: Decimal
    shown: str  # the price as the page printed it, e.g. "$8.98"
    page: Page


_PRICE = re.compile(r"\$\s*(\d{1,3}(?:,\d{3})+|\d+)(\.\d{2})?")


def price_from(text: str) -> tuple[Decimal, str] | None:
    """The price a page prints ("$1,299.00", "$8.98"), as a number and as shown; None if it prints none."""
    m = _PRICE.search(text or "")
    if m is None:
        return None
    digits = m.group(1).replace(",", "") + (m.group(2) or "")
    amount = Decimal(digits)
    return amount, f"${amount.quantize(Decimal('0.01'))}"


def rank(offers: list[Offer]) -> list[Offer]:
    """D16: cheapest first, by the price read from each store's page. The sort is stable,
    so a tie keeps store order."""
    return sorted(offers, key=lambda offer: offer.price)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())


def names_product(text: str, name: str, size: str) -> bool:
    """A search result names the product: every word of its name, and its size."""
    words = _words(text)
    size_words = _words(size)
    if not all(w in words for w in _words(name)):
        return False
    return any(words[i : i + len(size_words)] == size_words for i in range(len(words)))


def either(names: list[str]) -> str:
    """"Target, Walmart or Amazon"."""
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} or {names[-1]}"


BUY_STEP = "Could not reach the checkout"


class ProductChore(BaseChore):
    """D16-D18: the product at each store, each in its own tab; the ranked card with Buy on
    the cheapest; Buy adds it to that store's cart, reaches checkout with the address and
    the card on file, and pauses at Place order behind the Confirm gate."""

    def __init__(self, *args: Any, prices: Any = None) -> None:
        super().__init__(*args)
        self.offers: list[Offer] = []
        self.prices = prices  # live mode with a shopping search configured (D40); None in tests
        self.listings: list[Any] = []

    @property
    def product(self) -> str:
        return f"{self.fields['name']}, {self.fields['size']}"

    @property
    def begin_step(self) -> str:
        return f"Could not search the stores for {self.fields.get('name')}"

    async def _begin(self) -> None:
        if self.prices is not None:
            await self._begin_real()
            return
        name, size = str(self.fields["name"]), str(self.fields["size"])
        query = f"{name} {size}"
        found: list[Offer] = []
        not_found: list[str] = []
        first: Page | None = None
        for store in self.sites.stores:
            tab = await self.hands.new_tab()
            first = first or tab
            offer = await self._find(store, tab, query, name, size)
            if offer is None:
                not_found.append(store.name)  # D17: nothing is bought there
            else:
                found.append(offer)
        card = self.desk.card
        card.not_found = not_found
        if not found:
            # D17: no store answered; the card says so and offers no Buy.
            self.page = first
            if first is not None:
                await self.hands.focus(first)
            raise StepFailed(f"Not found at {either([s.name for s in self.sites.stores])}")
        self.offers = rank(found)
        card.ranking = [{"store": o.store.name, "price": o.shown, "link": o.page.url} for o in self.offers]
        cheapest = self.offers[0]
        self.page = cheapest.page
        await self.hands.focus(cheapest.page)
        card.buy = cheapest.store.name
        card.controls = ["Buy"]

    async def _begin_real(self) -> None:
        """D40 (live): real listings from a shopping search, the lowest per store, each opened in
        its own tab; the card ranks them and offers Buy, which opens the cheapest for the user."""
        name, size = str(self.fields["name"]), self.fields.get("size")
        query = f"{name} {size}" if size else name
        try:
            self.listings = self.prices.search(query)
        except Exception as err:  # the search service, not a page: a failed step, nothing bought
            raise StepFailed(f"Could not search the stores for {name}") from err
        card = self.desk.card
        if not self.listings:
            raise StepFailed(f"Not found at any store for {name}")
        first: Page | None = None
        tabs: list[Page] = []
        for listing in self.listings:
            tab = await self.hands.new_tab()
            first = first or tab
            tabs.append(tab)
            try:
                await tab.goto(listing.link, wait_until="domcontentloaded")
            except PlaywrightError:
                pass  # the listing's page may refuse an automated browser; the tab stays, the price stands
        card.not_found = []
        card.ranking = [{"store": l.store, "price": l.shown, "link": l.link} for l in self.listings]
        self.page = tabs[0] if tabs else first
        if self.page is not None:
            await self.hands.focus(self.page)
        card.buy = self.listings[0].store
        card.controls = ["Buy"]

    async def _find(self, store: Store, tab: Page, query: str, name: str, size: str) -> Offer | None:
        """The store's search, then the product's own page and the price it shows; None when the
        store does not list it or its page cannot be reached (D17)."""
        try:
            response = await tab.goto(store.search(query))
            if response is None or response.status >= 400 or not (await response.body()).strip():
                return None
            results = tab.locator(store.result)
            hit = None
            for i in range(await results.count()):
                if names_product(await results.nth(i).inner_text(), name, size):
                    hit = results.nth(i)
                    break
            if hit is None:
                return None
            async with tab.expect_navigation() as navigation:
                await hit.click()
            response = await navigation.value
            if response is None or response.status >= 400:
                return None
            price = tab.locator(store.price)
            if await price.count() == 0:
                return None
            read = price_from(await price.first.inner_text())
        except PlaywrightError:
            return None
        if read is None:
            return None
        return Offer(store=store, price=read[0], shown=read[1], page=tab)

    async def tap(self, control: str) -> bool:
        if self.stopped or control != "Buy" or "Buy" not in self.desk.card.controls:
            return False
        await self._run(BUY_STEP, self._buy)
        return True

    async def say(self, text: str) -> bool:
        if re.match(r"^\s*buy\b", text, re.IGNORECASE):
            return await self.tap("Buy")
        return False

    async def _buy(self) -> None:
        """D18: the cheapest store's cart, its checkout with the address and the card on file
        filled, and the pause before Place order (D7). With real listings (D40) Buy opens the
        cheapest listing for the user and the chore ends there: the checkout is theirs."""
        if self.prices is not None and self.listings:
            listing = self.listings[0]
            card = self.desk.card
            card.controls = []
            card.buy = None
            if self.page is not None:
                await self.hands.focus(self.page)
                card.link = self.page.url
            self.stopped = True
            self.desk.report(f"Opened the {listing.store} listing, {listing.shown}; the checkout is yours")
            return
        offer = self.offers[0]
        store = offer.store
        card = self.desk.card
        card.controls = []
        card.buy = None
        page = offer.page
        self.page = page
        await self.hands.focus(page)
        async with page.expect_navigation() as navigation:
            await page.click(store.add_to_cart)
        await self._answered(await navigation.value, f"Could not add the product to the {store.name} cart")
        if await page.locator(store.checkout_link).count() == 0:
            raise StepFailed(f"Could not add the product to the {store.name} cart", page.url)
        async with page.expect_navigation() as navigation:
            await page.click(store.checkout_link)
        await self._answered(await navigation.value, f"Could not reach the {store.name} checkout")
        items = page.locator(store.cart_item)
        listed = [await items.nth(i).inner_text() for i in range(await items.count())]
        if not any(names_product(item, str(self.fields["name"]), str(self.fields["size"])) for item in listed):
            raise StepFailed(f"The {store.name} cart does not hold the {self.product}", page.url)
        await page.fill(store.ship_name, SHIP_TO.name)
        await page.fill(store.ship_street, SHIP_TO.street)
        await page.fill(store.ship_city, SHIP_TO.city)
        await page.fill(store.ship_state, SHIP_TO.state)
        await page.fill(store.ship_zip, SHIP_TO.zip)
        await page.fill(store.card_number, CARD_ON_FILE.number)
        await page.fill(store.card_expiry, CARD_ON_FILE.expiry)
        await page.fill(store.card_cvc, CARD_ON_FILE.cvc)
        card.link = page.url
        refused = f"The {store.name} checkout did not take the order"
        self.desk.pause_for_confirm(
            lambda: self._run(refused, self._place, offer, refused),
            f"Ready to order from {store.name}, {offer.shown}, waiting for you",
        )

    async def _place(self, offer: Offer, refused: str) -> None:
        """Runs only from Desk.confirm (the Confirm gate); the store's receipt is what says it is done."""
        assert self.page is not None
        await self.hands.submit_final(self.page, offer.store.place, self.desk)
        if await self.page.locator(offer.store.receipt).count() == 0:
            raise StepFailed(refused, self.page.url)
        self.desk.card.link = self.page.url
        self.desk.report(f"Ordered from {offer.store.name}, {offer.shown}")  # D19: completed after Confirm


CHORES = {"ticket": TicketChore, "bill": BillChore, "product": ProductChore}


def chore_for(hands: Hands, sites: SiteMap, eye: Any, prices: Any = None):
    def make(desk: Desk, ident: Identification) -> BaseChore:
        if ident.kind == "product" and prices is not None:
            return ProductChore(hands, sites, desk, eye, ident, prices=prices)
        return CHORES[ident.kind](hands, sites, desk, eye, ident)

    return make
