"""The report (D19, D20, D21): what the card and the texts say when a chore ends.

A chore ends three ways: completed after Confirm, paused at Confirm, or stopped at a
failed step. Each end puts what was done on the card (beside what was identified,
the deadline and the link the chore already keeps there) and sends exactly one text
with the same summary and the deadline. A chore with a deadline also gets one
day-before text, at nine in the morning the day before (D20); a product gets none (D21).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.desk.deadlines import human_date

# A stable namespace for idempotency keys: the same event of the same chore always gets
# the same key; a new chore (a new hold-up, even of the same ticket) gets new ones.
_KEYS = uuid.UUID("6f0c1c1e-8a63-4c55-9d3e-2b1d6f1a9e70")


@dataclass(frozen=True)
class Reminder:
    at: datetime  # when it goes, on the desk's clock
    until: datetime  # when it is dropped unsent: the deadline day has begun
    body: str
    key: str


def chore_name(kind: str, fields: dict[str, Any]) -> str | None:
    """How a text names the chore: "citation 4512087733", "the LADWP bill"; a product needs no name."""
    if kind == "ticket" and fields.get("citation"):
        return f"citation {fields['citation']}"
    if kind == "bill" and fields.get("biller"):
        return f"the {fields['biller']} bill"
    return None


def chore_key(kind: str, fields: dict[str, Any]) -> str:
    """What one chore is, for idempotency: the same thing held up names the same chore."""
    if kind == "ticket":
        return f"ticket:{fields.get('citation')}"
    if kind == "bill":
        return f"bill:{fields.get('biller')}:{fields.get('account')}"
    return f"{kind}:{fields.get('name')}:{fields.get('size')}"


def new_chore_id() -> str:
    """One chore instance: each hold-up that begins a chore gets its own."""
    return uuid.uuid4().hex


def event_key(chore: str, chore_id: str, event: str) -> str:
    """A stable idempotency key per chore event: a resend of the same event of the same
    chore instance is the same message; another hold-up of the same thing is a new chore
    with new keys, so a rehearsal never swallows the demo's text (risk-3)."""
    return str(uuid.uuid5(_KEYS, f"{chore}#{chore_id}|{event}"))


def report_text(done: str, deadline: str | None, note: str | None) -> str:
    """The one text at a chore's end: what was done and the deadline."""
    if deadline is None:
        return f"{done}. No deadline."
    due = f"Due {human_date(deadline)}"
    if note:
        due += f" ({note})"
    return f"{done}. {due}."


def reminder_text(name: str, deadline: str) -> str:
    """The day-before text (D20): names the chore and says the deadline is tomorrow."""
    return f"Reminder: the deadline for {name} is tomorrow, {human_date(deadline)}."
