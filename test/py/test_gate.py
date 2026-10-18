"""The Confirm gate's one code path (D7): Hands.submit_final is the only place in the app
that presses a pay, buy or submit button, it refuses unless the desk is confirmed, and
Desk.confirm is reached only from POST /confirm and POST /say."""

import asyncio
import re
from pathlib import Path

import pytest

from app.desk import Desk, GateClosed
from app.hands import Hands
from app.hands.sitemap import FinalSubmit

APP = Path(__file__).resolve().parents[2] / "app"


def _sources():
    return {p.relative_to(APP).as_posix(): p.read_text(encoding="utf-8") for p in APP.rglob("*.py")}


def test_submit_final_refuses_an_unconfirmed_desk_before_touching_the_page():
    class Page:
        def __getattr__(self, name):
            raise AssertionError(f"the page was touched ({name}) before the gate")

    with pytest.raises(GateClosed):
        asyncio.run(Hands().submit_final(Page(), FinalSubmit("#submit"), Desk()))


def test_only_submit_final_presses_a_final_submit():
    pressers = []
    for name, text in _sources().items():
        for m in re.finditer(r"\.click\(([^)]*)\)", text):
            pressers.append((name, m.group(1).strip()))
    # Every click in the app: lookups and links, and the one gated press.
    assert ("hands/__init__.py", "button.selector") in pressers
    for name, arg in pressers:
        if arg == "button.selector":
            assert name == "hands/__init__.py"
        else:
            assert "submit" not in arg.lower() and "order" not in arg.lower(), (name, arg)
    readers = [name for name, text in _sources().items() if ".selector" in text and "FinalSubmit" in text]
    assert readers == ["hands/__init__.py"]


def test_confirm_is_called_only_by_the_tap_and_the_spoken_yes():
    callers = [(name, line.strip()) for name, text in _sources().items() for line in text.splitlines() if "desk.confirm()" in line or "self.confirm()" in line]
    assert sorted(callers) == sorted(
        [
            ("web/server.py", "if not await desk.confirm():"),
            ("desk/state.py", "return await self.confirm()"),
        ]
    )
    state = _sources()["desk/state.py"]
    # The spoken yes is the only path inside the desk, and it sits behind the yes matcher.
    assert re.search(r"if _YES\.match\(text\):\s*\n\s*return await self\.confirm\(\)", state)
    assert "self.confirmed = True" in state and state.count("self.confirmed = True") == 1
