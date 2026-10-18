"""The report (D19, D20, D21) on the desk, without a browser: one text at every chore end,
one day-before text at nine in the morning on the desk's clock, none for a product."""

import asyncio
from datetime import datetime, timedelta

import pytest

from app.desk import Desk, FakeTexts, VirtualClock
from app.desk.deadlines import REMINDER_TIME, deadline_for, human_date, reminder_at
from app.desk.report import chore_key, event_key, report_text
from app.eye import Identification

START = datetime(2026, 10, 17, 0, 0, 0)
TICKET = {"city": "Los Angeles", "citation": "4512087733", "plate": "8ABC123", "issued": "2026-10-12", "due": "2026-11-02"}
BILL = {"biller": "LADWP", "account": "1234567890", "amount": "148.22", "due": "2026-11-05", "phone": "1-800-342-5397"}
PRODUCT = {"name": "Cholula Original hot sauce", "brand": "Cholula", "size": "32 oz"}


def _desk(kind, fields, start=START):
    clock, texts = VirtualClock(start), FakeTexts()
    desk = Desk(clock=clock, texts=texts)
    desk.identification = Identification(kind=kind, fields=dict(fields), confidence=1.0)
    desk.card.identified = {"kind": kind, "fields": dict(fields)}
    desk.card.deadline, desk.card.deadline_note = deadline_for(kind, fields)
    return desk, clock, texts


def _advance(desk, clock, seconds):
    clock.advance(seconds)
    asyncio.run(desk.tick(clock.now()))


def _until(clock, at):
    return (at - clock.now()).total_seconds()


def test_deadlines_per_kind():
    assert deadline_for("ticket", TICKET) == ("2026-11-02", None)
    assert deadline_for("ticket", {**TICKET, "due": None}) == ("2026-11-02", "counted 21 days from the issue date")
    assert deadline_for("bill", BILL) == ("2026-11-05", None)
    assert deadline_for("product", PRODUCT) == (None, None)
    assert deadline_for("product", {**PRODUCT, "due": "2026-11-05"}) == (None, None)


def test_the_day_before_text_goes_at_nine_local_the_day_before():
    assert REMINDER_TIME.hour == 9 and REMINDER_TIME.minute == 0
    assert reminder_at("2026-11-02") == datetime(2026, 11, 1, 9, 0)
    assert reminder_at("2026-10-19") == datetime(2026, 10, 18, 9, 0)
    assert reminder_at("2027-01-01") == datetime(2026, 12, 31, 9, 0)
    assert human_date("2026-11-02") == "Nov 2, 2026"


def test_every_end_sends_exactly_one_text_with_the_summary_and_the_deadline():
    desk, clock, texts = _desk("ticket", TICKET)
    desk.report("Ready to pay citation 4512087733, waiting for you")
    assert desk.card.done == "Ready to pay citation 4512087733, waiting for you"
    assert [(t["body"], t["at"]) for t in texts.sent] == [("Ready to pay citation 4512087733, waiting for you. Due Nov 2, 2026.", "2026-10-17T00:00:00")]
    clock.advance(30)
    desk.report("Paid citation 4512087733")
    assert desk.card.done == "Paid citation 4512087733"
    assert [(t["body"], t["at"]) for t in texts.sent[1:]] == [("Paid citation 4512087733. Due Nov 2, 2026.", "2026-10-17T00:00:30")]


def test_the_text_says_how_a_counted_deadline_was_counted():
    assert report_text("Ready to pay citation 4512087734, waiting for you", "2026-11-02", "counted 21 days from the issue date") == (
        "Ready to pay citation 4512087734, waiting for you. Due Nov 2, 2026 (counted 21 days from the issue date)."
    )
    assert report_text("Ordered from Walmart, $8.98", None, None) == "Ordered from Walmart, $8.98. No deadline."


@pytest.mark.parametrize(
    "kind, fields, name, day_before",
    [("ticket", TICKET, "citation 4512087733", datetime(2026, 11, 1, 9)), ("bill", BILL, "the LADWP bill", datetime(2026, 11, 4, 9))],
)
def test_d20_the_second_text_goes_at_nine_the_day_before_and_not_a_second_earlier(kind, fields, name, day_before):
    desk, clock, texts = _desk(kind, fields)
    desk.report("Ready to pay, waiting for you")
    assert len(texts.sent) == 1
    _advance(desk, clock, _until(clock, day_before) - 1)
    assert len(texts.sent) == 1, texts.sent
    _advance(desk, clock, 1)
    assert len(texts.sent) == 2
    second = texts.sent[1]
    assert second["at"] == day_before.isoformat()
    assert name in second["body"] and "is tomorrow" in second["body"]
    # One second text only: the deadline day and the days after bring no more.
    _advance(desk, clock, 5 * 86400)
    assert len(texts.sent) == 2


def test_d20_a_clock_that_jumps_past_nine_sends_it_once_stamped_when_it_went():
    desk, clock, texts = _desk("ticket", TICKET)
    desk.report("Ready to pay citation 4512087733, waiting for you")
    _advance(desk, clock, _until(clock, datetime(2026, 11, 1, 10, 30)))
    assert [t["at"] for t in texts.sent[1:]] == ["2026-11-01T10:30:00"]


def test_d20_one_second_text_per_chore_however_many_ends():
    desk, clock, texts = _desk("ticket", TICKET)
    desk.report("Ready to pay citation 4512087733, waiting for you")
    desk.report("Paid citation 4512087733")
    # Through the day before (when the second text goes) and on past the deadline.
    _advance(desk, clock, _until(clock, datetime(2026, 11, 1, 12)))
    _advance(desk, clock, _until(clock, datetime(2026, 11, 3)))
    assert [t["body"].startswith("Reminder") for t in texts.sent] == [False, False, True]


def test_d20_no_second_text_when_nine_the_day_before_has_passed():
    desk, clock, texts = _desk("ticket", {**TICKET, "due": "2026-10-17"})
    desk.report("Ready to pay citation 4512087733, waiting for you")
    _advance(desk, clock, 3 * 86400)
    assert len(texts.sent) == 1


def test_d21_a_product_gets_no_second_text_in_thirty_days():
    desk, clock, texts = _desk("product", PRODUCT)
    desk.report("Ordered from Walmart, $8.98")
    assert [t["body"] for t in texts.sent] == ["Ordered from Walmart, $8.98. No deadline."]
    for _ in range(30):
        _advance(desk, clock, 86400)
    assert len(texts.sent) == 1 and desk.reminders == []


def test_d21_a_product_with_a_date_on_its_card_still_gets_no_second_text():
    desk, clock, texts = _desk("product", PRODUCT)
    desk.card.deadline = "2026-10-20"  # never set by a chore; the kind alone rules it out
    desk.report("Ordered from Walmart, $8.98")
    _advance(desk, clock, 30 * 86400)
    assert len(texts.sent) == 1


def test_a_reset_drops_the_waiting_second_text():
    desk, clock, texts = _desk("ticket", TICKET)
    desk.report("Ready to pay citation 4512087733, waiting for you")
    desk.reset()
    _advance(desk, clock, 30 * 86400)
    assert len(texts.sent) == 1


def _begun(desk):
    """The chore begins on the desk, the way a hold-up begins it (Desk._begin)."""
    desk.chores = lambda d, i: _Chore()
    asyncio.run(desk._begin())


def test_the_idempotency_key_is_stable_per_chore_event():
    desk, clock, texts = _desk("ticket", TICKET)
    _begun(desk)
    desk.report("Ready to pay citation 4512087733, waiting for you")
    desk.report("Paid citation 4512087733")
    assert texts.sent[1]["key"] != texts.sent[0]["key"]
    # The same chore and event give the same key: a resend of one event is one message.
    chore = desk.chore_id
    assert chore is not None
    assert texts.sent[0]["key"] == event_key(chore_key("ticket", TICKET), chore, "end:Ready to pay citation 4512087733, waiting for you")
    assert event_key(chore_key("ticket", TICKET), chore, "reminder:2026-11-02") == event_key(chore_key("ticket", TICKET), chore, "reminder:2026-11-02")
    assert event_key(chore_key("ticket", TICKET), chore, "reminder:2026-11-02") != event_key(
        chore_key("ticket", {**TICKET, "citation": "4512087735"}), chore, "reminder:2026-11-02"
    )


def test_risk_3_two_hold_ups_of_the_same_citation_give_different_keys():
    # risk-3: three rehearsals to the Confirm pause and then the demo, each with citation
    # 4512087733, must each deliver: a new chore is a new message, never a duplicate.
    keys = []
    for _ in range(4):
        desk, clock, texts = _desk("ticket", TICKET)
        _begun(desk)
        desk.report("Ready to pay citation 4512087733, waiting for you")
        keys.append(texts.sent[0]["key"])
    assert len(set(keys)) == 4, keys
    # The same desk, reset and the ticket held up again: a new chore, new keys.
    desk, clock, texts = _desk("ticket", TICKET)
    _begun(desk)
    desk.report("Ready to pay citation 4512087733, waiting for you")
    first, reminder = texts.sent[0]["key"], desk.reminders[0].key
    desk.reset()
    desk.identification = Identification(kind="ticket", fields=dict(TICKET), confidence=1.0)
    desk.card.deadline, desk.card.deadline_note = deadline_for("ticket", TICKET)
    _begun(desk)
    desk.report("Ready to pay citation 4512087733, waiting for you")
    assert texts.sent[1]["key"] != first
    assert desk.reminders[0].key != reminder


def test_risk_2_a_day_before_text_is_never_sent_on_or_after_the_deadline_day():
    # risk-2: a clock that first moves past nine the day before only on the deadline day
    # (or later) drops the reminder; "the deadline is tomorrow" would be false.
    desk, clock, texts = _desk("ticket", {**TICKET, "due": "2026-10-19"}, start=datetime(2026, 10, 17, 12, 0))
    desk.report("Paid citation 4512087733")
    assert len(desk.reminders) == 1
    _advance(desk, clock, 3 * 86400)
    assert [t["body"] for t in texts.sent] == ["Paid citation 4512087733. Due Oct 19, 2026."]
    assert desk.reminders == []
    _advance(desk, clock, 86400)
    assert len(texts.sent) == 1


@pytest.mark.parametrize("at, sent", [(datetime(2026, 10, 18, 23, 59, 59), True), (datetime(2026, 10, 19, 0, 0), False), (datetime(2026, 10, 19, 9, 0), False)])
def test_risk_2_the_day_before_text_goes_only_while_it_is_still_the_day_before(at, sent):
    desk, clock, texts = _desk("ticket", {**TICKET, "due": "2026-10-19"}, start=datetime(2026, 10, 17, 12, 0))
    desk.report("Paid citation 4512087733")
    _advance(desk, clock, _until(clock, at))
    assert [t["body"].startswith("Reminder") for t in texts.sent] == ([False, True] if sent else [False])


class _SlowEye:
    """An eye whose answer takes `seconds` on the clock it is given (live, the real clock moves during the call)."""

    def __init__(self, clock, seconds, answer):
        self.clock, self.seconds, self.answer = clock, seconds, answer

    def identify(self, frame):
        self.clock.advance(self.seconds)
        return self.answer


class _Chore:
    def __init__(self):
        self.begun = 0

    async def begin(self):
        self.begun += 1


@pytest.mark.parametrize("seconds, named", [(4.9, True), (5, True), (5.5, False), (8, False)])
def test_live_an_eye_slower_than_five_seconds_on_the_clock_is_hold_it_closer(seconds, named):
    clock = VirtualClock(START)
    chore = _Chore()
    answer = Identification(kind="ticket", fields=dict(TICKET), confidence=1.0)
    desk = Desk(eye=_SlowEye(clock, seconds, answer), chores=lambda d, i: chore, clock=clock)
    asyncio.run(desk.take_frame(b"x", "image/jpeg", clock.now()))
    asyncio.run(desk.tick(clock.now() + timedelta(seconds=0)))
    assert (desk.card.identified is not None) is named
    assert chore.begun == (1 if named else 0)
    assert desk.card.notice == (None if named else "Hold it closer")
