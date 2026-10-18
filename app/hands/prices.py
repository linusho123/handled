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
# Retailers a shopper knows rank first; a seller named like a bare domain ranks after them.
RETAILERS = frozenset({"amazon", "amazon.com", "walmart", "target", "best buy", "bestbuy", "costco", "sam's club", "home depot", "the home depot", "lowe's", "staples", "office depot", "newegg", "micro center", "b&h photo", "b&h photo video", "b&h", "adorama", "apple", "jbl", "harman", "samsung", "sony", "bose", "verizon", "at&t", "t-mobile", "kohl's", "macy's", "nordstrom", "gamestop", "rei", "dick's sporting goods", "cvs", "walgreens", "kroger", "ralphs", "vons", "albertsons", "safeway", "instacart", "whole foods", "trader joe's", "cholula", "dell", "hp", "lenovo", "microsoft", "google store", "nike", "adidas", "ikea", "wayfair", "overstock", "chewy", "petco", "petsmart", "ulta", "sephora", "guitar center", "sweetwater", "crutchfield", "abt", "qvc", "hsn", "zappos", "bed bath & beyond", "michaels", "joann", "hobby lobby", "ace hardware", "harbor freight", "autozone", "o'reilly", "advance auto parts", "7-eleven", "dollar general", "five below", "big lots", "bj's", "meijer", "h-e-b", "publix", "wegmans", "lululemon", "patagonia", "the north face", "columbia", "under armour", "gap", "old navy", "uniqlo", "h&m", "zara", "shop apple", "apple.com", "walmart.com", "target.com", "bestbuy.com", "jbl.com", "costco.com"})
_DOMAINISH = re.compile(r"\.(com|net|org|co|io|ir|shop|store|xyz|info|biz|ru|cn|uk|de|fr|ca|us)\b", re.IGNORECASE)
_USED = re.compile(r"\b(used|pre-?owned|refurb(ished)?|open box|renewed|second ?hand)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Listing:
    store: str
    price: Decimal
    shown: str
    link: str
    title: str


_GENERIC = frozenset({"portable", "bluetooth", "wireless", "speaker", "speakers", "the", "and", "with", "for", "of", "a", "an", "new", "pack", "oz", "fl", "ml", "count", "ct", "original", "edition", "black", "white", "blue", "red", "pro", "plus", "max", "mini", "gen", "generation", "2nd", "3rd", "usb", "c", "cable", "charger", "case"})


def _tokens(text: str) -> frozenset[str]:
    """The words that name a product: letters-and-digits tokens, minus generic ones. A listing
    must carry every one of the query's to count (so "Flip 4" never stands in for "Clip 4")."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return frozenset(w for w in words if w not in _GENERIC and (len(w) > 1 or w.isdigit()))


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
        retail: dict[str, Listing] = {}  # known retailers, new items
        shops: dict[str, Listing] = {}  # other named shops, new items
        other: dict[str, Listing] = {}  # marketplaces, used items, bare-domain sellers
        several: Listing | None = None  # Google's own aggregated entry: the product at several stores, "from $x"
        wanted = _tokens(query)
        for item in data.get("shopping_results") or []:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "")
            if wanted and not wanted <= _tokens(title):
                continue  # a look-alike (Flip 4 for Clip 4, a case, a bundle of something else)
            source = str(item.get("source") or "").strip()
            store = source.split(" - ")[0].strip()  # "eBay - someseller" is eBay
            raw = item.get("extracted_price")
            try:
                price = Decimal(str(raw))
            except (InvalidOperation, TypeError, ValueError):
                continue
            if price <= 0:
                continue
            if not store:
                if item.get("multiple_sources") or str(item.get("price") or "").endswith("+"):
                    # The product at several stores; Google shows the lowest. The link is the
                    # shopping search for it, where the stores are listed.
                    link = "https://www.google.com/search?tbm=shop&q=" + urllib.parse.quote_plus(title)
                    candidate = Listing(store="Several stores", price=price, shown=f"from ${price.quantize(Decimal('0.01'))}", link=link, title=title)
                    if several is None or candidate.price < several.price:
                        several = candidate
                continue
            tags = " ".join(str(x) for x in (item.get("extensions") or [])) + " " + title + " " + str(item.get("second_hand_condition") or "")
            link = str(item.get("product_link") or item.get("link") or "")
            listing = Listing(store=store, price=price, shown=f"${price.quantize(Decimal('0.01'))}", link=link, title=title)
            key = store.lower()
            if key in MARKETPLACES or _USED.search(tags) or (key not in RETAILERS and _DOMAINISH.search(key)):
                bucket = other
                if _USED.search(tags) or str(item.get("second_hand_condition") or ""):
                    listing = Listing(store=f"{store} (used)", price=price, shown=listing.shown, link=link, title=title)
                    store = listing.store
            elif key in RETAILERS:
                bucket = retail
            else:
                bucket = shops
            if store not in bucket or listing.price < bucket[store].price:
                bucket[store] = listing
        # Known retailers' new items first, then other named shops, then marketplaces and used
        # listings, each tier cheapest first, until three stores are named.
        ranked: list[Listing] = []
        if several is not None:
            ranked.append(several)
        for tier in (retail, shops, other):
            if len(ranked) >= stores:
                break
            taken = {r.store for r in ranked}
            ranked += sorted((l for l in tier.values() if l.store not in taken), key=lambda l: l.price)[: stores - len(ranked)]
        return ranked
