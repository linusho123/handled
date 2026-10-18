"""The bill chore (D14, D15, D7, D26) on the fixture biller, in process: the payment page
filled and paused; only Confirm pays, and only the biller's receipt says it is paid; no page
found, a page that does not answer and a login wall each pay nothing and show "call to pay"
with the number the bill prints, which comes from the identification's fields, never from a
page (the fixture biller's pages print their own customer-service number as a decoy)."""

import asyncio
import socket

import pytest
import uvicorn
from fixture_sites import Sites
from fixture_sites.ladwp import SITE_PHONE

from app.desk import Desk, FakeTexts, GateClosed, VirtualClock
from app.eye import Identification
from app.hands import Hands
from app.hands.chores import BillChore, amount_shown
from app.hands.sitemap import SiteMap
from app.web.server import create_app

BILL = {"biller": "LADWP", "account": "1234567890", "amount": "148.22", "due": "2026-11-05", "phone": "1-800-342-5397"}
# A bill that prints another number: a card showing the fixture's 1-800-342-5397 for it,
# or the site's own number, read it from somewhere other than the bill.
OTHER_PHONE = "1-213-555-0147"


def test_amount_shown():
    assert amount_shown("148.22") == "$148.22"
    assert amount_shown("9.5") == "$9.50"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run(body, fields=BILL, sitemap=None):
    async def main():
        hands, sites, desk = Hands(headless=True, step_timeout_ms=5_000), Sites(), Desk(texts=FakeTexts())
        api = create_app(clock=VirtualClock(), desk=desk, hands=hands, texts=desk.texts, sites=sites, test_mode=True)
        port = _free_port()
        server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
        task = asyncio.create_task(server.serve())
        try:
            while not server.started:
                await asyncio.sleep(0.02)
            ident = Identification(kind="bill", fields=dict(fields))
            desk.identification = ident
            desk.card.identified = {"kind": "bill", "fields": dict(fields)}
            sm = SiteMap(f"http://127.0.0.1:{port}")
            if sitemap is not None:
                sitemap(sm)
            chore = BillChore(hands, sm, desk, None, ident)
            desk.chore = chore
            await body(chore, desk, sites, hands, port)
        finally:
            server.should_exit = True
            await task

    asyncio.run(main())


def test_the_payment_page_is_filled_and_only_confirm_pays():
    async def body(chore, desk, sites, hands, port):
        await chore.begin()
        page = hands.pages[0]
        assert page.url.endswith("/sites/ladwp/pay")
        assert await page.input_value("#account") == "1234567890"
        assert await page.input_value("#amount") == "148.22"
        assert desk.card.controls == ["Confirm"] and desk.waiting_for_confirm
        assert desk.card.done == "Ready to pay LADWP $148.22, waiting for you"
        assert desk.card.deadline == "2026-11-05" and desk.card.call_to_pay is None
        assert sites["ladwp"].ledger == []
        # Past the gate without Confirm, Pay now refuses before touching the page.
        with pytest.raises(GateClosed):
            await chore._pay("refused")
        assert sites["ladwp"].ledger == []
        assert await desk.confirm()
        assert [(e["account"], e["amount"]) for e in sites["ladwp"].ledger] == [("1234567890", "148.22")]
        assert desk.card.done == "Paid LADWP $148.22"
        assert [t["body"] for t in desk.texts.sent] == ["Ready to pay LADWP $148.22, waiting for you. Due Nov 5, 2026.", "Paid LADWP $148.22. Due Nov 5, 2026."]

    _run(body)


@pytest.mark.parametrize(
    ("fault", "step", "where"),
    [
        ("nopage", "No payment page for LADWP was found", "/sites/ladwp/search"),
        ("down", "Could not reach the LADWP payment page", "/sites/ladwp/pay"),
        ("login", "The LADWP page asks for a login", "/sites/ladwp/login"),
    ],
)
def test_no_reachable_page_shows_the_number_the_bill_prints(fault, step, where):
    async def body(chore, desk, sites, hands, port):
        sites["ladwp"].set_fault(fault)
        await chore.begin()
        assert desk.card.failed_step == step
        assert desk.card.call_to_pay == OTHER_PHONE != SITE_PHONE
        assert desk.card.done == f"{step}: call to pay {OTHER_PHONE}"
        assert desk.card.controls == [] and not desk.waiting_for_confirm
        assert len(hands.pages) == 1 and hands.pages[0].url.split("?")[0].endswith(where)
        assert desk.card.link == hands.pages[0].url
        assert sites["ladwp"].ledger == []
        assert [t["body"] for t in desk.texts.sent] == [f"{step}: call to pay {OTHER_PHONE}. Due Nov 5, 2026."]

    _run(body, fields={**BILL, "phone": OTHER_PHONE})


def test_the_site_search_finds_the_payment_page_when_the_known_url_moved():
    """The SiteMap's URL for the page is stale: the biller's own search leads to it, and it pauses."""

    def moved(sm):
        biller = sm.billers["ladwp"]
        sm.billers["ladwp"] = type(biller)(**{**biller.__dict__, "pay_url": biller.pay_url.replace("/pay", "/payments")})

    async def body(chore, desk, sites, hands, port):
        await chore.begin()
        assert hands.pages[0].url.endswith("/sites/ladwp/pay")
        assert desk.card.controls == ["Confirm"]
        assert sites["ladwp"].ledger == []

    _run(body, sitemap=moved)


def test_a_bill_with_no_printed_number_stops_with_the_step_alone():
    async def body(chore, desk, sites, hands, port):
        sites["ladwp"].set_fault("down")
        await chore.begin()
        assert desk.card.call_to_pay is None
        assert desk.card.done == desk.card.failed_step == "Could not reach the LADWP payment page"
        assert SITE_PHONE not in desk.card.done

    _run(body, fields={**BILL, "phone": None})


def test_a_biller_the_sitemap_does_not_know_is_call_to_pay():
    """Browser Use, the finder for an unknown biller, is deferred (P4): the chore stops at once."""

    async def body(chore, desk, sites, hands, port):
        await chore.begin()
        assert desk.card.failed_step == "No payment page is known for Acme Water"
        assert desk.card.call_to_pay == OTHER_PHONE
        assert hands.pages == []
        assert sites["ladwp"].ledger == []

    _run(body, fields={**BILL, "biller": "Acme Water", "phone": OTHER_PHONE})


def test_a_payment_the_biller_refuses_is_a_failed_step_never_paid():
    async def body(chore, desk, sites, hands, port):
        await chore.begin()
        sites["ladwp"].set_fault("nopage")  # the payment page is gone when Pay now is pressed
        assert await desk.confirm()
        assert sites["ladwp"].ledger == []
        assert desk.card.failed_step == "The LADWP page did not take the payment"
        # head-1: Pay now was pressed, so the card does not say "call to pay"; the step and the link.
        assert desk.card.done == "The LADWP page did not take the payment"
        assert desk.card.call_to_pay is None
        assert desk.card.link == hands.pages[0].url

    _run(body)


def test_head_1_a_failure_after_pay_now_is_pressed_never_says_call_to_pay():
    """head-1: once Pay now has posted, the chore cannot know that nothing was paid, so a
    receipt it cannot find shows the step and the browser link, never "call to pay" (D15
    covers only stops before the gate)."""

    def no_receipt(sm):
        biller = sm.billers["ladwp"]
        sm.billers["ladwp"] = type(biller)(**{**biller.__dict__, "receipt": "#no-such-receipt"})

    async def body(chore, desk, sites, hands, port):
        await chore.begin()
        assert await desk.confirm()
        assert [(e["account"], e["amount"]) for e in sites["ladwp"].ledger] == [("1234567890", "148.22")]
        assert desk.card.failed_step == "The LADWP page did not take the payment"
        assert desk.card.call_to_pay is None
        assert "call to pay" not in desk.card.done
        assert desk.card.done == "The LADWP page did not take the payment"
        assert desk.card.link == hands.pages[0].url
        assert all("call to pay" not in t["body"] for t in desk.texts.sent)

    _run(body, sitemap=no_receipt)
