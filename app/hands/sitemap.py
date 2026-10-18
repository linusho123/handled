"""The SiteMap: the URL and the selectors per site (BUILD-PLAN.md, "Architecture").

HANDLED_SITES=fixtures (tests) points at the fixture sites the test server
hosts under /sites/<site>/; the real pages arrive at the demo integration (PD).
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


@dataclass(frozen=True)
class Biller:
    name: str
    pay_url: str


@dataclass(frozen=True)
class Store:
    name: str
    search_url: str  # with {q}

    def search(self, query: str) -> str:
        return self.search_url.format(q=quote_plus(query))


class SiteMap:
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
        self.billers = {"ladwp": Biller(name="LADWP", pay_url=f"{sites}/ladwp/pay")}
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
