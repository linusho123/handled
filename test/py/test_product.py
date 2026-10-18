"""The product chore (D16-D18) on the fixture stores, in process: the prices are read from
each store's product page, ranked cheapest first with a tie in store order; a store that
does not list it is "not found"; Buy reaches checkout and pauses; only Confirm orders, and
only the store's receipt says it is ordered."""

import asyncio
import socket
from decimal import Decimal

import pytest
import uvicorn
from fixture_sites import Sites

from app.desk import Desk, FakeTexts, GateClosed, VirtualClock
from app.eye import Identification
from app.hands import Hands
from app.hands.chores import Offer, ProductChore, either, names_product, price_from, rank
from app.hands.sitemap import SiteMap, Store
from app.web.server import create_app

SLUG = "cholula-original-32oz"


def test_price_from_reads_the_printed_price():
    assert price_from("$8.98") == (Decimal("8.98"), "$8.98")
    assert price_from("Now $1,299.00 each") == (Decimal("1299.00"), "$1299.00")
    assert price_from("$999") == (Decimal("999"), "$999.00")
    assert price_from("Price unavailable") is None
    assert price_from("") is None


def test_rank_is_by_the_number_with_a_tie_in_store_order():
    def offer(name, price):
        return Offer(store=Store(name=name, search_url=""), price=Decimal(price), shown=f"${price}", page=None)

    ranked = rank([offer("Target", "999.00"), offer("Walmart", "8.98"), offer("Amazon", "10.99")])
    assert [o.store.name for o in ranked] == ["Walmart", "Amazon", "Target"]  # by number, not by text
    tied = rank([offer("Target", "8.98"), offer("Walmart", "8.98"), offer("Amazon", "0.01")])
    assert [o.store.name for o in tied] == ["Amazon", "Target", "Walmart"]


def test_a_result_names_the_product_by_every_word_and_the_size():
    assert names_product("Cholula Original Hot Sauce, 32 oz", "Cholula Original hot sauce", "32 oz")
    assert not names_product("Cholula Original Hot Sauce, 12 oz", "Cholula Original hot sauce", "32 oz")
    assert not names_product("Cholula Chipotle Hot Sauce, 32 oz", "Cholula Original hot sauce", "32 oz")
    assert either(["Target", "Walmart", "Amazon"]) == "Target, Walmart or Amazon"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run(body):
    async def main():
        hands, sites, desk = Hands(headless=True, step_timeout_ms=5_000), Sites(), Desk(texts=FakeTexts())
        api = create_app(clock=VirtualClock(), desk=desk, hands=hands, texts=desk.texts, sites=sites, test_mode=True)
        port = _free_port()
        server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
        task = asyncio.create_task(server.serve())
        try:
            while not server.started:
                await asyncio.sleep(0.02)
            ident = Identification(kind="product", fields={"name": "Cholula Original hot sauce", "size": "32 oz"})
            desk.identification = ident
            chore = ProductChore(hands, SiteMap(f"http://127.0.0.1:{port}"), desk, None, ident)
            desk.chore = chore
            await body(chore, desk, sites, hands)
        finally:
            server.should_exit = True
            await task

    asyncio.run(main())


def test_the_ranking_is_the_prices_the_pages_show_and_buy_pauses_before_the_order():
    async def body(chore, desk, sites, hands):
        sites["target"].set_prices({SLUG: "999.00"})
        sites["walmart"].set_prices({SLUG: "8.98"})
        sites["amazon"].set_prices({SLUG: "10.99"})
        await chore.begin()
        assert [(r["store"], r["price"]) for r in desk.card.ranking] == [("Walmart", "$8.98"), ("Amazon", "$10.99"), ("Target", "$999.00")]
        assert desk.card.not_found == [] and desk.card.buy == "Walmart" and desk.card.controls == ["Buy"]
        assert len(hands.pages) == 3
        assert await chore.tap("Buy")
        assert desk.card.controls == ["Confirm"] and desk.waiting_for_confirm
        assert sites["walmart"].ledger == []
        # Past the gate without Confirm, Place order refuses before touching the page.
        with pytest.raises(GateClosed):
            await chore._place(chore.offers[0], "refused")
        assert sites["walmart"].ledger == []
        assert await desk.confirm()
        assert [e["total"] for e in sites["walmart"].ledger] == ["8.98"]
        assert desk.card.done == "Ordered from Walmart, $8.98"

    _run(body)


def test_an_order_the_store_refuses_is_a_failed_step_never_ordered():
    async def body(chore, desk, sites, hands):
        sites["walmart"].set_prices({SLUG: "8.98"})
        await chore.begin()
        assert desk.card.not_found == ["Target", "Amazon"]
        assert await chore.tap("Buy")
        sites["walmart"].set_fault("nolisting")  # the store no longer sells it: Place order is refused
        assert await desk.confirm()
        assert sites["walmart"].ledger == []
        assert desk.card.failed_step == "The Walmart checkout did not take the order"
        assert desk.card.done == "The Walmart checkout did not take the order"

    _run(body)


def test_a_store_that_does_not_answer_is_not_found():
    async def body(chore, desk, sites, hands):
        sites["target"].set_prices({SLUG: "1.00"})
        sites["target"].set_fault("down")
        sites["amazon"].set_prices({SLUG: "10.99"})
        await chore.begin()
        assert [r["store"] for r in desk.card.ranking] == ["Amazon"]
        assert desk.card.not_found == ["Target", "Walmart"]

    _run(body)
