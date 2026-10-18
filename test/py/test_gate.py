"""The Confirm gate's one code path (D7): Hands.submit_final is the only place in the app
that presses a pay, buy or submit button, it refuses unless the desk is confirmed, and
Desk.confirm is reached only from POST /confirm and POST /say."""

import ast
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


def _trees():
    return {name: ast.parse(text, filename=name) for name, text in _sources().items()}


def _where(tree):
    """Each node with the qualified name of the function (or class) it sits in."""
    out = []

    def walk(node, scope):
        for child in ast.iter_child_nodes(node):
            inner = scope
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                inner = f"{scope}.{child.name}" if scope else child.name
            out.append((child, scope))
            walk(child, inner)

    walk(tree, "")
    return out


def _confirm_references():
    """Every reference to the confirm attribute in app/: `x.confirm`, `Desk.confirm`,
    getattr(x, "confirm"), a bare `confirm` name, the string "confirm"."""
    refs = []
    for name, tree in _trees().items():
        for node, scope in _where(tree):
            if isinstance(node, ast.Attribute) and node.attr == "confirm":
                refs.append((name, scope, node.lineno))
            elif isinstance(node, ast.Name) and node.id == "confirm":
                refs.append((name, scope, node.lineno))
            elif isinstance(node, ast.Constant) and node.value == "confirm":
                refs.append((name, scope, node.lineno))
    return refs


def test_head_1_confirm_is_referenced_only_by_post_confirm_and_the_spoken_yes():
    refs = [(name, scope) for name, scope, _ in _confirm_references()]
    assert sorted(refs) == sorted([("web/server.py", "create_app.confirm"), ("desk/state.py", "Desk.say")]), _confirm_references()
    # The POST /confirm handler is the route the page's Confirm button posts to.
    server = _sources()["web/server.py"]
    assert re.search(r'@api\.post\("/confirm"\)\s*\n\s*async def confirm\(\)', server)


# Anything that runs code later, on its own: a timer, a delayed sleep, a thread.
_SCHEDULERS = {"call_later", "call_at", "Timer", "Thread", "run_coroutine_threadsafe", "call_soon_threadsafe", "start_new_thread", "scheduler", "enter", "enterabs"}


def _schedulers():
    found = []
    for name, tree in _trees().items():
        for node, scope in _where(tree):
            if isinstance(node, ast.Attribute) and node.attr in _SCHEDULERS:
                found.append((name, scope, node.attr, node.lineno))
            elif isinstance(node, ast.Name) and node.id in _SCHEDULERS:
                found.append((name, scope, node.id, node.lineno))
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if alias.name.split(".")[0] in ("threading", "sched", "_thread") or (isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in ("threading", "sched", "_thread")):
                        found.append((name, scope, f"import {alias.name}", node.lineno))
            elif isinstance(node, ast.Call):
                func = node.func
                called = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
                if called == "sleep":
                    zero = len(node.args) == 1 and not node.keywords and isinstance(node.args[0], ast.Constant) and node.args[0].value == 0
                    if not zero:
                        found.append((name, scope, "sleep", node.lineno))
    return found


def test_head_1_the_app_schedules_nothing_in_real_time():
    """The backstop to the virtual loop: no timer, delayed sleep or thread anywhere in
    app/, so nothing can tap Confirm (or do anything else) on its own later."""
    assert _schedulers() == []


@pytest.mark.parametrize(
    "probe",
    [
        "loop.call_later(0.3, lambda: loop.create_task(self.confirm()))",
        "loop.create_task(Desk.confirm(self))",
        "threading.Timer(0.3, print).start()",
        "await asyncio.sleep(0.3)",
        "f = getattr(self, 'confirm')",
    ],
)
def test_head_1_the_scans_catch_the_reviewers_probes(probe, monkeypatch):
    """The two scans above turn red on each spelling the head reviewer used."""
    real = _sources()
    patched = dict(real)
    patched["desk/state.py"] = real["desk/state.py"].replace(
        "        self.card.controls = [\"Confirm\"]\n", "        self.card.controls = [\"Confirm\"]\n        " + probe + "\n", 1
    )
    assert patched["desk/state.py"] != real["desk/state.py"]
    monkeypatch.setitem(globals(), "_sources", lambda: patched)
    assert _schedulers() != [] or [r for r in _confirm_references() if r[1] == "Desk.pause_for_confirm"]
