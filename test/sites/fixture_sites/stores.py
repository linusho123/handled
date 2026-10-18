"""target, walmart, amazon: three store fronts, one shape, as fixtures.

  GET  /search?q=        results: each catalog product whose name holds every word of q and that the store lists
  GET  /product/<slug>   the product page with its price
  POST /cart             adds a product to the store's cart (no ledger entry: nothing is bought)
  GET  /cart             the cart
  GET  /checkout         shipping address, card, Place order
  POST /order            places the order: the ledger records {"kind": "order", …}

A store lists a product only at a price set for the scenario (POST /test/sites
{"site", "prices": {slug: "9.49"}}); with no price set it lists nothing.
Faults: `nolisting` (the store lists nothing, whatever its prices), `down`
(every page answers nothing).
"""

from __future__ import annotations

import hashlib
import re

from decimal import Decimal, InvalidOperation
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse, Response

from fixture_sites.base import Site, SiteError, esc, last4, page

# What a store could carry. Which of these a store lists, and at what price, is set per scenario.
CATALOG: dict[str, str] = {
    "cholula-original-32oz": "Cholula Original Hot Sauce, 32 oz",
    "cholula-original-12oz": "Cholula Original Hot Sauce, 12 oz",
}


def _money(value: Any) -> str:
    try:
        amount = Decimal(str(value).strip().lstrip("$"))
        if not amount.is_finite() or amount < 0:
            raise InvalidOperation
        return f"{amount.quantize(Decimal('0.01'))}"
    except InvalidOperation as err:
        raise SiteError(f"not a price: {value!r}") from err


class StoreSite(Site):
    faults = frozenset({"nolisting", "down"})

    def __init__(self, name: str, title: str) -> None:
        super().__init__()
        self.name = name
        self.title = title
        self.prices: dict[str, str] = {}
        self.cart: list[str] = []
        # Live demo only (never in tests): a store lists anything searched for, at a stable made-up
        # price per store, so whatever the eye names ranks across the three stores (D38's fixtures).
        self.open_catalog = False
        self.extra: dict[str, str] = {}  # the listings an open catalog made up, slug to name

    def reset(self) -> None:
        super().reset()
        self.prices = {}
        self.cart = []
        self.extra = {}

    def _name(self, slug: str) -> str:
        return CATALOG.get(slug) or self.extra.get(slug) or slug

    def _make_up(self, words: list[str], query: str) -> tuple[str, str, str] | None:
        """An open catalog's listing for a query nobody stocked: a slug from the words, the query
        as the name, a price from a hash of the slug (the same every time) plus a store offset."""
        if not self.open_catalog or not words or self.fault == "nolisting":
            return None
        slug = "-".join(re.sub(r"[^a-z0-9]", "", w) for w in words)[:60].strip("-") or "item"
        if slug not in self.extra:
            base = 3 + int(hashlib.md5(slug.encode()).hexdigest(), 16) % 1500 / 100  # $3.00 to $17.99
            offset = int(hashlib.md5(f"{slug}:{self.name}".encode()).hexdigest(), 16) % 300 / 100  # the store's own $0 to $2.99
            self.extra[slug] = query.strip()
            self.prices[slug] = _money(base + offset)
        return slug, self.extra[slug], self.prices[slug]

    def set_prices(self, prices: dict[str, Any]) -> None:
        unknown = [slug for slug in prices if slug not in CATALOG]
        if unknown:
            raise SiteError(f"{self.name} has no product {unknown[0]!r}; the catalog is {', '.join(CATALOG)}")
        self.prices = {slug: _money(price) for slug, price in prices.items()}

    def describe(self) -> dict[str, Any]:
        return {**super().describe(), "prices": dict(self.prices)}

    def _listed(self, slug: str) -> str | None:
        if self.fault == "nolisting":
            return None
        return self.prices.get(slug)

    def router(self) -> APIRouter:
        r = APIRouter()
        base = f"/sites/{self.name}"

        @r.get("/")
        def home(request: Request) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            return page(
                self.title,
                f"<form method='get' action='{base}/search'><label>Search <input name='q' id='q'></label>"
                "<button type='submit'>Search</button></form>",
            )

        @r.get("/search")
        def search(request: Request, q: str = "") -> Response:
            if blocked := self.fault_response(request):
                return blocked
            words = [w for w in q.lower().replace(",", " ").split() if w]
            hits = [
                (slug, name, price)
                for slug, name in {**CATALOG, **self.extra}.items()
                if words and all(w in name.lower() for w in words) and (price := self._listed(slug)) is not None
            ]
            if not hits and (made := self._make_up(words, q)) is not None:
                hits = [made]
            items = "".join(
                f"<li class='result'><a href='{base}/product/{slug}'>{esc(name)}</a> <span class='price'>${price}</span></li>"
                for slug, name, price in hits
            )
            body = f"<ul id='results'>{items}</ul>" if hits else "<p id='no-results'>No results</p>"
            return page(f"{self.title} - Search: {q}", body)

        @r.get("/product/{slug}")
        def product(request: Request, slug: str) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            price = self._listed(slug)
            if price is None:
                return page(f"{self.title} - Not found", "<p>This item is not available.</p>", 404)
            return page(
                f"{self.title} - {self._name(slug)}",
                f"<p id='name'>{esc(self._name(slug))}</p><p><span id='price' class='price' data-price='{price}'>${price}</span></p>"
                f"<form method='post' action='{base}/cart'><input type='hidden' name='slug' value='{esc(slug)}'>"
                "<button type='submit' id='add-to-cart'>Add to cart</button></form>",
            )

        @r.post("/cart")
        def add_to_cart(request: Request, slug: str = Form(...)) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            if self._listed(slug) is None:
                return page(f"{self.title} - Not found", "<p>This item is not available.</p>", 404)
            self.cart.append(slug)
            return RedirectResponse(f"{base}/cart", status_code=303)

        @r.get("/cart")
        def cart(request: Request) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            items = "".join(f"<li class='cart-item' data-slug='{esc(s)}'>{esc(self._name(s))}</li>" for s in self.cart)
            checkout = f"<a id='checkout' href='{base}/checkout'>Check out</a>" if self.cart else ""
            return page(f"{self.title} - Cart", f"<ul id='cart'>{items}</ul>{checkout}")

        @r.get("/checkout")
        def checkout(request: Request) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            items = "".join(f"<li class='cart-item' data-slug='{esc(s)}'>{esc(self._name(s))}</li>" for s in self.cart)
            return page(
                f"{self.title} - Checkout",
                f"<ul id='cart'>{items}</ul><form method='post' action='{base}/order'>"
                "<label>Full name <input name='ship_name' id='ship_name'></label>"
                "<label>Street <input name='ship_street' id='ship_street'></label>"
                "<label>City <input name='ship_city' id='ship_city'></label>"
                "<label>State <input name='ship_state' id='ship_state'></label>"
                "<label>ZIP <input name='ship_zip' id='ship_zip'></label>"
                "<label>Card number <input name='card_number' id='card_number'></label>"
                "<label>Expiry <input name='card_expiry' id='card_expiry'></label>"
                "<label>CVC <input name='card_cvc' id='card_cvc'></label>"
                "<button type='submit' id='place-order'>Place order</button></form>",
            )

        @r.post("/order")
        def order(
            request: Request,
            ship_name: str = Form(...),
            ship_street: str = Form(...),
            ship_city: str = Form(...),
            ship_state: str = Form(...),
            ship_zip: str = Form(...),
            card_number: str = Form(...),
            card_expiry: str = Form(...),
            card_cvc: str = Form(...),
        ) -> Response:
            if blocked := self.fault_response(request):
                return blocked
            ship = {"name": ship_name, "street": ship_street, "city": ship_city, "state": ship_state, "zip": ship_zip}
            if not self.cart:
                return page(f"{self.title} - Checkout", "<p role='alert'>Your cart is empty.</p>", 400)
            if not (all(v.strip() for v in ship.values()) and last4(card_number) and card_expiry.strip() and card_cvc.strip()):
                return page(f"{self.title} - Checkout", "<p role='alert'>Every field is required.</p>", 400)
            # The store sells only what it lists now: an item it no longer lists (its price
            # gone, or `nolisting` set after Add to cart) refuses the whole order.
            listed = {s: self._listed(s) for s in self.cart}
            if any(price is None for price in listed.values()):
                return page(f"{self.title} - Checkout", "<p role='alert'>An item in your cart is no longer available.</p>", 400)
            items = [{"slug": s, "name": self._name(s), "price": listed[s]} for s in self.cart]
            total = _money(sum(Decimal(i["price"]) for i in items))
            self.record({"kind": "order", "items": items, "total": total, "ship_to": {k: v.strip() for k, v in ship.items()}, "card_last4": last4(card_number)})
            self.cart = []
            return page(f"{self.title} - Order placed", f"<p id='receipt'>Order placed, ${total}.</p>")

        return r
