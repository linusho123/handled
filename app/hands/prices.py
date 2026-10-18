"""Real prices for the product chore, live mode only (the operator's ruling of 2026-10-18, D40).

A shopping search (SerpApi's Google Shopping engine) answers one query with listings from many
sellers. The chore keeps the lowest listing per store, ranks the stores cheapest first, and opens
each listing in its own tab. Buy opens the cheapest listing for the user; the cart, the checkout
and the Confirm pause for products run only against the fixture stores (D40). Never used in tests.
"""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

SERPAPI = "https://serpapi.com/search.json"

# Resale marketplaces and used-goods sellers rank after retailers: a demo's cheapest listing
# should be a new item from a store, not a reseller's used one (seen 2026-10-18: eBay, Mercari).
MARKETPLACES = frozenset({"ebay", "mercari", "mercari.com", "poshmark", "offerup", "aliexpress", "temu", "wish", "etsy", "facebook marketplace", "craigslist", "back market", "swappa", "reebelo", "gazelle", "alibaba", "dhgate", "shein"})
_USED = re.compile(r"\b(used|pre-?owned|refurb(ished)?|open box|renewed|second ?hand)\b", re.IGNORECASE)


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
        retail: dict[str, Listing] = {}
        other: dict[str, Listing] = {}
        for item in data.get("shopping_results") or []:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source") or "").strip()
            store = source.split(" - ")[0].strip()  # "eBay - someseller" is eBay
            raw = item.get("extracted_price")
            try:
                price = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if not store or price <= 0:
                continue
            title = str(item.get("title") or "")
            tags = " ".join(str(x) for x in (item.get("extensions") or [])) + " " + title + " " + str(item.get("second_hand_condition") or "")
            link = str(item.get("product_link") or item.get("link") or "")
            listing = Listing(store=store, price=price, shown=f"${price.quantize(Decimal('0.01'))}", link=link, title=title)
            bucket = other if (store.lower() in MARKETPLACES or _USED.search(tags)) else retail
            if store not in bucket or listing.price < bucket[store].price:
                bucket[store] = listing
        # New items from retailers first; marketplaces and used listings only fill the gaps.
        ranked = sorted(retail.values(), key=lambda l: l.price)[:stores]
        if len(ranked) < stores:
            ranked += sorted((l for l in other.values() if l.store not in {r.store for r in ranked}), key=lambda l: l.price)[: stores - len(ranked)]
        return ranked
