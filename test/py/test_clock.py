import asyncio
from datetime import datetime

import pytest

from app.desk import Card, Desk, FakeTexts, VirtualClock
from app.eye import Identification


def test_the_virtual_clock_moves_only_when_told():
    clock = VirtualClock()
    assert clock.now() == datetime(2026, 10, 17)
    assert clock.now() == datetime(2026, 10, 17)
    assert clock.advance(5.1) == datetime(2026, 10, 17, 0, 0, 5, 100000)
    assert clock.reset(datetime(2026, 10, 31, 9)) == datetime(2026, 10, 31, 9)
    with pytest.raises(ValueError):
        clock.advance(-1)


class UnknownEye:
    def identify(self, frame):
        return Identification(kind="unknown")


def test_the_desk_starts_empty_and_an_unreadable_frame_identifies_nothing():
    desk = Desk(eye=UnknownEye())
    empty = {
        "identified": None, "done": None, "deadline": None, "deadline_note": None, "link": None, "controls": [],
        "question": None, "letter": None, "notice": None, "failed_step": None, "call_to_pay": None, "ranking": [], "not_found": [], "buy": None,
    }
    assert desk.state() == empty
    asyncio.run(desk.take_frame(b"\x89PNG", "image/png", datetime(2026, 10, 17)))
    assert desk.state() == empty
    assert not desk.waiting_for_confirm
    desk.card.done = "something"
    desk.reset()
    assert desk.state() == Card().document() == empty


def test_the_texts_fake_records_and_resets():
    texts = FakeTexts()
    assert texts.sent == []
    texts.send("hello", "2026-10-17T00:00:00")
    assert [t["body"] for t in texts.sent] == ["hello"]
    texts.reset()
    assert texts.sent == []
