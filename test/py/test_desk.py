"""The desk's five-second clock (D4, D5) and the Confirm gate (D7, D6), without a browser."""

import asyncio
from datetime import datetime, timedelta

import pytest

from app.desk import HOLD_IT_CLOSER, Desk, GateClosed
from app.eye import Identification

T0 = datetime(2026, 10, 17, 9, 0, 0)
TICKET = Identification(kind="ticket", fields={"citation": "4512087733"}, confidence=1.0)


class Eye:
    def __init__(self, answer):
        self.answer = answer
        self.calls = 0

    def identify(self, frame):
        self.calls += 1
        return self.answer


class Chore:
    def __init__(self):
        self.begun = 0

    async def begin(self):
        self.begun += 1

    async def tap(self, control):
        return False

    async def say(self, text):
        return False


def _desk(answer, delay=0.0):
    chore = Chore()
    desk = Desk(eye=Eye(answer), chores=lambda d, i: chore)
    desk.eye_delay = delay
    return desk, chore


def _at(desk, seconds):
    asyncio.run(desk.tick(T0 + timedelta(seconds=seconds)))


@pytest.mark.parametrize("delay", [0, 1, 4.9, 5])
def test_an_answer_within_five_seconds_names_the_thing_and_begins_its_chore(delay):
    desk, chore = _desk(TICKET, delay)
    asyncio.run(desk.take_frame(b"x", "image/png", T0))
    _at(desk, 5)
    assert desk.card.identified == {"kind": "ticket", "fields": {"citation": "4512087733"}}
    assert desk.card.notice is None and chore.begun == 1


@pytest.mark.parametrize("delay", [5.1, 20])
def test_an_answer_after_five_seconds_is_hold_it_closer_and_never_a_chore(delay):
    desk, chore = _desk(TICKET, delay)
    asyncio.run(desk.take_frame(b"x", "image/png", T0))
    _at(desk, 4.9)
    assert desk.card.notice is None
    _at(desk, 5)
    assert desk.card.notice == HOLD_IT_CLOSER
    _at(desk, 60)
    assert desk.card.identified is None and chore.begun == 0


def test_an_unreadable_thing_is_hold_it_closer_at_five_seconds_not_before():
    desk, chore = _desk(Identification(kind="unknown"))
    asyncio.run(desk.take_frame(b"x", "image/png", T0))
    _at(desk, 4.9)
    assert desk.card.notice is None
    _at(desk, 5)
    assert desk.card.notice == HOLD_IT_CLOSER and chore.begun == 0


def test_a_question_holds_the_chore_until_it_is_answered():
    product = Identification(kind="product", fields={"name": "Cholula Original Hot Sauce", "size": None, "size_guess": "32 oz"}, variant_question="Is this the 32 oz?")
    desk, chore = _desk(product)
    asyncio.run(desk.take_frame(b"x", "image/png", T0))
    assert desk.card.question == "Is this the 32 oz?" and chore.begun == 0
    assert asyncio.run(desk.say("no, the 12"))
    assert desk.card.question is None
    assert desk.card.identified["fields"]["size"] == "12 oz"
    assert chore.begun == 1


def test_the_gate_runs_its_step_only_on_confirm_and_never_on_the_clock():
    desk, _ = _desk(TICKET)
    ran = []

    async def step():
        desk.require_confirmed()
        ran.append(True)

    desk.pause_for_confirm(step)
    assert desk.card.controls == ["Confirm"] and desk.waiting_for_confirm
    for seconds in (60, 3600, 3 * 86400):
        _at(desk, seconds)
    assert ran == [] and desk.waiting_for_confirm
    assert not asyncio.run(desk.say("no"))
    assert not asyncio.run(desk.say("yes, but wait"))
    assert ran == []
    assert asyncio.run(desk.say("yes"))
    assert ran == [True] and not desk.waiting_for_confirm and not desk.confirmed


def test_a_step_past_the_gate_refuses_without_confirm():
    desk, _ = _desk(TICKET)
    with pytest.raises(GateClosed):
        desk.require_confirmed()
    assert not asyncio.run(desk.confirm())  # nothing is waiting


def test_confirm_is_not_a_tap_control():
    desk, _ = _desk(TICKET)
    desk.pause_for_confirm(lambda: None)
    assert not asyncio.run(desk.tap("Confirm"))
    assert desk.waiting_for_confirm


@pytest.mark.parametrize("jump_to", [5.1, 6, 20])
def test_a_late_answer_is_refused_even_when_the_clock_jumps_past_it(jump_to):
    # A coarse clock (the real one ticks when it ticks) can pass five seconds and the
    # eye's late answer in one step: the answer still came after the five seconds.
    desk, chore = _desk(TICKET, 5.1)
    asyncio.run(desk.take_frame(b"x", "image/png", T0))
    _at(desk, jump_to)
    assert desk.card.notice == HOLD_IT_CLOSER
    assert desk.card.identified is None and chore.begun == 0
