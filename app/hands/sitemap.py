"""The SiteMap: the URL and the selectors per site (BUILD-PLAN.md, "Architecture").

HANDLED_SITES=fixtures (tests) points at the fixture sites the test server
hosts under /sites/<site>/. HANDLED_SITES=real (live mode's default) reads the
real pages' URLs and selectors from REAL below; the operator confirms them
against the live pages at the demo integration (PD) and writes them here.
A form's final submit (the step that pays, files or orders) is a FinalSubmit:
only Hands.submit_final presses one, and only after Confirm.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class FinalSubmit:
    """The button that lets money leave or files something. Pressed only through the Confirm gate."""

    selector: str


@dataclass(frozen=True)
class CityPortal:
    city: str
    lookup_url: str
    citation_field: str
    plate_field: str
    lookup_button: str  # looks a citation up; pays and files nothing
    found: str  # present on the citation's own page
    pay_link: str
    contest_link: str
    card_name: str
    card_number: str
    card_expiry: str
    card_cvc: str
    amount: str
    pay: FinalSubmit
    letter: str
    contest: FinalSubmit
    receipt: str
    login_wall: str = "input[type=password]"
    captcha_field: str = ""  # a CAPTCHA box before the lookup goes on; "" when the page has none (D36)
    lookup_choice: str = ""  # a radio to pick before the lookup (Los Angeles: citation number, not payment plan)


@dataclass(frozen=True)
class Biller:
    """A biller's payment page (D14, D15). The selectors default to the fixture biller's
    (test/sites/fixture_sites/ladwp.py). With no payment page at `pay_url` the chore tries
    the biller's own site search for one (`search_url`, with {q}); a result whose words say
    pay is followed. Nothing here holds a phone number: the number to call is the one the
    bill prints (the identification's fields), never one a page shows."""

    name: str
    pay_url: str
    search_url: str | None = None  # the biller's own site search, with {q}
    search_result: str = ".result a"  # a search result's link
    account: str = "#account"  # present only on the payment page
    amount: str = "#amount"
    card_name: str = "#card_name"
    card_number: str = "#card_number"
    card_expiry: str = "#card_expiry"
    card_cvc: str = "#card_cvc"
    pay: FinalSubmit = FinalSubmit("#submit")  # Pay now: pressed only after Confirm
    receipt: str = "#receipt"  # present only once the biller has taken the payment
    login_wall: str = "input[type=password]"

    def search(self, query: str) -> str | None:
        return self.search_url.format(q=quote_plus(query)) if self.search_url else None


@dataclass(frozen=True)
class Store:
    """A store front (D16, D18): its search, the product page's price, the cart and the
    checkout. The selectors default to the fixture stores' (test/sites/fixture_sites/stores.py)."""

    name: str
    search_url: str  # with {q}
    result: str = ".result a"  # a search result's link to its product page
    price: str = "#price"  # the price the product page shows
    add_to_cart: str = "#add-to-cart"  # puts the product in the cart; buys nothing
    checkout_link: str = "#checkout"  # from the cart to the checkout page
    cart_item: str = ".cart-item"  # an item the checkout page lists
    ship_name: str = "#ship_name"
    ship_street: str = "#ship_street"
    ship_city: str = "#ship_city"
    ship_state: str = "#ship_state"
    ship_zip: str = "#ship_zip"
    card_number: str = "#card_number"
    card_expiry: str = "#card_expiry"
    card_cvc: str = "#card_cvc"
    place: FinalSubmit = FinalSubmit("#place-order")  # Place order: pressed only after Confirm
    receipt: str = "#receipt"  # present only once the store has taken the order

    def search(self, query: str) -> str:
        return self.search_url.format(q=quote_plus(query))


# The real sites (HANDLED_SITES=real). Los Angeles pays and contests parking citations through
# its ETIMS vendor pages, read on 2026-10-18 at the demo integration: the pay-by-web lookup
# (form inputForm: a paymentType radio, documentNum up to 16 characters, a CAPTCHA, Submit) and
# the online initial-review form (complaintform.jsp?complainttype=6: ticket up to 11 characters,
# a CAPTCHA). Neither has a plate field. The pages after the CAPTCHA are unconfirmed (D37): no
# real citation was in hand, so those selectors stay placeholders, and a selector that does not
# match is a failed step on the card (the browser stays), never a guess typed elsewhere.
REAL = {
    "la_lookup_url": "https://wmq.etimspayments.com/pbw/include/la/input.jsp",
    "la_contest_url": "https://wmq.etimspayments.com/pbw/include/la/complaintform.jsp?complainttype=6",
    "la": {
        "citation_field": "input[name=documentNum]",  # confirmed 2026-10-18
        "plate_field": "",  # the real page has no plate box (confirmed)
        "lookup_choice": "input[name=paymentType][value=T]",  # citation number, not payment plan (confirmed)
        "captcha_field": "#captchaSText",  # confirmed: the user types it (D36)
        "lookup_button": "input[name=submit]",  # confirmed; pays and files nothing
        "found": "text=/amount due/i",  # UNCONFIRMED (D37): the citation's own page
        "pay_link": "text=/^pay/i",  # UNCONFIRMED (D37)
        "contest_link": "text=/initial review/i",  # UNCONFIRMED (D37)
        "card_name": "input[name=cardholderName]",  # UNCONFIRMED (D37)
        "card_number": "input[name=cardNumber]",  # UNCONFIRMED (D37)
        "card_expiry": "input[name=expiration]",  # UNCONFIRMED (D37)
        "card_cvc": "input[name=cvv]",  # UNCONFIRMED (D37)
        "amount": "input[name=amount]",  # UNCONFIRMED (D37)
        "pay": "input[type=submit]",  # UNCONFIRMED (D37): the final Pay button (FinalSubmit: pressed only after Confirm)
        "letter": "textarea",  # UNCONFIRMED (D37)
        "contest": "input[type=submit]",  # UNCONFIRMED (D37): the final contest button (FinalSubmit)
        "receipt": "text=/confirmation/i",  # UNCONFIRMED (D37)
    },
    "ladwp_pay_url": "https://www.ladwp.com/account/payments",
    # PD: the biller's site search, and every biller selector (Biller above) is the
    # fixture default until PD reads the live page and writes the real ones here.
    "ladwp_search_url": "https://www.ladwp.com/search?keys={q}",
    # PD: the stores' search URLs; every other store selector is the fixture default
    # (Store above) until PD reads each live page and writes the real ones here.
    "stores": [
        ("Target", "https://www.target.com/s?searchTerm={q}"),
        ("Walmart", "https://www.walmart.com/search?q={q}"),
        ("Amazon", "https://www.amazon.com/s?k={q}"),
    ],
}


class SiteMap:
    @classmethod
    def real(cls) -> "SiteMap":
        """The real sites (live mode, HANDLED_SITES=real), from REAL."""
        sites = cls.__new__(cls)
        la = REAL["la"]
        assert isinstance(la, dict)
        sites.cities = {
            "los angeles": CityPortal(
                city="Los Angeles",
                lookup_url=str(REAL["la_lookup_url"]),
                **{k: v for k, v in la.items() if k not in ("pay", "contest")},
                pay=FinalSubmit(la["pay"]),
                contest=FinalSubmit(la["contest"]),
            )
        }
        sites.billers = {"ladwp": Biller(name="LADWP", pay_url=str(REAL["ladwp_pay_url"]), search_url=str(REAL["ladwp_search_url"]))}
        sites.stores = [Store(name=name, search_url=url) for name, url in REAL["stores"]]  # type: ignore[misc]
        return sites

    def __init__(self, base_url: str) -> None:
        base = base_url.rstrip("/")
        sites = f"{base}/sites"
        self.cities = {
            "los angeles": CityPortal(
                city="Los Angeles",
                lookup_url=f"{sites}/la-citations/",
                citation_field="#citation",
                plate_field="#plate",
                lookup_button="#lookup",
                found="#citation-number",
                pay_link="#pay",
                contest_link="#contest",
                card_name="#card_name",
                card_number="#card_number",
                card_expiry="#card_expiry",
                card_cvc="#card_cvc",
                amount="#amount",
                pay=FinalSubmit("#submit"),
                letter="#letter",
                contest=FinalSubmit("#submit"),
                receipt="#receipt",
            )
        }
        self.billers = {"ladwp": Biller(name="LADWP", pay_url=f"{sites}/ladwp/pay", search_url=f"{sites}/ladwp/search?q={{q}}")}
        # Store order is the ranking's tie order (product.feature, D16): Target, Walmart, Amazon.
        self.stores = [
            Store(name="Target", search_url=f"{sites}/target/search?q={{q}}"),
            Store(name="Walmart", search_url=f"{sites}/walmart/search?q={{q}}"),
            Store(name="Amazon", search_url=f"{sites}/amazon/search?q={{q}}"),
        ]

    def city(self, name: str | None) -> CityPortal | None:
        return self.cities.get((name or "").strip().lower())

    def biller(self, name: str | None) -> Biller | None:
        return self.billers.get((name or "").strip().lower())
