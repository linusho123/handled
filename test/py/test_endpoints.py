"""The /test/* endpoints under malformed input and across a reset (risk-1, risk-2, risk-3).
The hands are a stand-in here: these tests are about the server's own handling, and
test_browser.py covers the real browser."""

import pytest
from fastapi.testclient import TestClient
from fixture_sites import Sites

from app.desk import Desk, FakeTexts, VirtualClock
from app.web.server import create_app

CARD = {"card_number": "4242 4242 4242 4242", "card_expiry": "12/30", "card_cvc": "123"}


class StandInHands:
    """Hands with no browser. `during_reset` runs while the reset awaits the old
    context's close: the moment a form post the old context already sent can land."""

    def __init__(self) -> None:
        self.during_reset = None

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def reset(self) -> None:
        if self.during_reset is not None:
            self.during_reset()

    async def view(self):
        return {"url": None, "title": None, "fields": {}, "tabs": []}


@pytest.fixture
def world():
    sites, hands, texts = Sites(), StandInHands(), FakeTexts()
    api = create_app(clock=VirtualClock(), desk=Desk(), hands=hands, texts=texts, sites=sites, test_mode=True)
    with TestClient(api, follow_redirects=False) as client:
        yield client, sites, hands, texts


def _raw_json(client, path, text):
    return client.post(path, content=text.encode(), headers={"content-type": "application/json"})


@pytest.mark.parametrize("seconds", ["Infinity", "-Infinity", "NaN", "1e18", "1e308"])
def test_risk_1_advance_refuses_a_number_the_clock_cannot_hold(world, seconds):
    client, *_ = world
    before = client.post("/test/reset").json()["now"]
    r = _raw_json(client, "/test/advance", '{"seconds": %s}' % seconds)
    assert r.status_code == 400, r.text
    assert client.post("/test/advance", json={"seconds": 0}).json()["now"] == before


@pytest.mark.parametrize("fault", [["x"], {"a": 1}, 3, True])
def test_risk_1_a_site_fault_that_is_not_a_name_is_a_400(world, fault):
    client, sites, *_ = world
    assert client.post("/test/sites", json={"site": "ladwp", "fault": fault}).status_code == 400
    assert sites["ladwp"].fault is None


@pytest.mark.parametrize("price", ["NaN", "Infinity", "-Infinity", "sNaN", "1e40"])
def test_risk_1_a_store_price_that_is_not_an_amount_is_a_400(world, price):
    client, sites, *_ = world
    r = client.post("/test/sites", json={"site": "walmart", "prices": {"cholula-original-32oz": price}})
    assert r.status_code == 400, r.text
    assert sites["walmart"].prices == {}


def test_risk_2_a_post_that_lands_while_the_hands_close_does_not_survive_the_reset(world):
    client, sites, hands, texts = world

    def late_post():
        # A pay form the old browser context sent before the reset, served while
        # the reset awaits that context's close.
        sites["la-citations"].record({"kind": "payment", "citation": "4512087733", "amount": "73.00", "card_last4": "4242", "card_name": ""})
        texts.send("late", "2026-10-17T00:00:00")

    hands.during_reset = late_post
    assert client.post("/test/reset").status_code == 200
    assert client.get("/test/sites/la-citations/ledger").json() == []
    assert client.get("/test/texts").json() == []


@pytest.mark.parametrize("start", ["2026-10-17T07:50+00:00", "2026-10-17T07:50:00-07:00", "2026-10-17T07:50Z"])
def test_risk_3_reset_refuses_a_start_with_a_timezone(world, start):
    client, *_ = world
    r = client.post("/test/reset", json={"start": start})
    assert r.status_code == 400, r.text
    assert client.post("/test/reset").json()["now"] == "2026-10-17T00:00:00"


def test_risk_3_reset_takes_a_naive_local_start(world):
    client, *_ = world
    assert client.post("/test/reset", json={"start": "2026-10-17T07:50"}).json()["now"] == "2026-10-17T07:50:00"
