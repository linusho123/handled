"""GET /test/browser is Playwright's own view of the browser the app drives: the page URL,
title and the field values read from the DOM, and every open tab. The browser is held
to loopback in test mode."""

import asyncio
import socket

import httpx
import pytest
import uvicorn
from fixture_sites import Sites

from app.desk import Desk, FakeTexts, VirtualClock
from app.hands import Hands
from app.web.server import create_app


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _with_app(body):
    hands = Hands(headless=True)
    api = create_app(clock=VirtualClock(), desk=Desk(), hands=hands, texts=FakeTexts(), sites=Sites(), test_mode=True)
    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
    task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.02)
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}") as client:
            await body(hands, client, f"http://127.0.0.1:{port}")
    finally:
        server.should_exit = True
        await task


def test_the_browser_view_is_read_from_the_dom():
    async def body(hands, client, base):
        assert (await client.get("/test/browser")).json() == {"url": None, "title": None, "fields": {}, "tabs": []}
        page = await hands.open(f"{base}/sites/la-citations/")
        await page.fill("#citation", "4512087733")
        await page.fill("#plate", "8ABC123")
        view = (await client.get("/test/browser")).json()
        assert view["url"] == f"{base}/sites/la-citations/"
        assert view["title"] == "City of Los Angeles - Parking Citations - Look up a citation"
        assert view["fields"] == {"citation": "4512087733", "plate": "8ABC123"}
        assert view["tabs"] == [{"url": view["url"], "title": view["title"]}]
        # Typing changes the DOM, and the view follows the DOM, not anything the app logged.
        await page.evaluate("document.querySelector('#plate').value = 'OTHER99'")
        assert (await client.get("/test/browser")).json()["fields"]["plate"] == "OTHER99"
        # A second tab: the view reads the newest, and lists both.
        await hands.open(f"{base}/sites/ladwp/pay")
        view = (await client.get("/test/browser")).json()
        assert view["url"] == f"{base}/sites/ladwp/pay"
        assert len(view["tabs"]) == 2
        # Reset closes every tab.
        assert (await client.post("/test/reset")).status_code == 200
        assert (await client.get("/test/browser")).json() == {"url": None, "title": None, "fields": {}, "tabs": []}

    asyncio.run(_with_app(body))


def test_a_browser_form_post_reaches_the_sites_ledger():
    async def body(hands, client, base):
        page = await hands.open(f"{base}/sites/la-citations/pay?citation=4512087733")
        assert (await client.get("/test/sites/la-citations/ledger")).json() == []
        await page.fill("#card_number", "4242424242424242")
        await page.fill("#card_expiry", "12/30")
        await page.fill("#card_cvc", "123")
        assert (await client.get("/test/sites/la-citations/ledger")).json() == []
        await page.click("#submit")
        await page.wait_for_selector("#receipt")
        assert (await client.get("/test/sites/la-citations/ledger")).json() == [
            {"kind": "payment", "citation": "4512087733", "amount": "73.00", "card_last4": "4242", "card_name": ""}
        ]

    asyncio.run(_with_app(body))


def test_the_test_browser_never_leaves_loopback():
    async def body(hands, client, base):
        with pytest.raises(Exception, match="ERR_BLOCKED_BY_CLIENT"):
            await hands.open("http://203.0.113.7/")  # TEST-NET-3: never routed, and never tried

    asyncio.run(_with_app(body))
