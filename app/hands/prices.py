"""Real prices for the product chore, live mode only (the operator's ruling of 2026-10-18, D40).

A shopping search (SerpApi's Google Shopping engine) answers one query with listings from many
sellers. The chore keeps the lowest listing per store, ranks the stores cheapest first, and opens
each listing in its own tab. Buy opens the cheapest listing for the user; the cart, the checkout
and the Confirm pause for products run only against the fixture stores (D40). Never used in tests.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SERPAPI = "https://serpapi.com/search.json"


@dataclass(frozen=True)
class Listing:
    store: str
    price: Decimal
    shown: str
    link: str
    title: str


class GoogleShoppingPrices:
    name = "google-shopping"

    def __init__(self, api_key: str, country: str = "us", language: str = "en") -> None:
        self._api_key = api_key
        self.country = country
        self.language = language

    def search(self, query: str, stores: int = 3) -> list[Listing]:
        """The lowest listing per store for the query, cheapest store first, at most `stores`."""
        params = {"engine": "google_shopping", "q": query, "gl": self.country, "hl": self.language, "api_key": self._api_key}
        request = urllib.request.Request(f"{SERPAPI}?{urllib.parse.urlencode(params)}", headers={"User-Agent": "handled/0.1"})
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.loads(response.read())
        best: dict[str, Listing] = {}
        for item in data.get("shopping_results") or []:
            if not isinstance(item, dict):
                continue
            store = str(item.get("source") or "").strip()
            raw = item.get("extracted_price")
            try:
                price = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not store or price <= 0:
                continue
            link = str(item.get("product_link") or item.get("link") or "")
            listing = Listing(store=store, price=price, shown=f"${price.quantize(Decimal('0.01'))}", link=link, title=str(item.get("title") or ""))
            if store not in best or listing.price < best[store].price:
                best[store] = listing
        return sorted(best.values(), key=lambda l: l.price)[:stores]
