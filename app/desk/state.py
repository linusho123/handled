"""The desk: the card the page renders, the five-second clock, and the Confirm gate.

GET /desk returns the card as one JSON document. After a reset every field is
empty. The desk starts the five-second clock at the frame (D4, D5): an
identification the eye delivers within five seconds names the thing on the
card and begins its chore; with none by then the card says "Hold it closer"
and nothing begins. The clock is the desk's Clock (virtual in test mode), and
in test mode the eye's latency is set on that clock (POST /test/eye).

The Confirm gate (D7, D6): a chore that reaches a pay, buy or submit step
pauses there (`pause_for_confirm`) with Confirm the only control. The paused
step runs only from `confirm()`, and `confirm()` is called only by a tap on
Confirm (POST /confirm) or a spoken yes (POST /say). Nothing else sets
`confirmed`: no timer, no clock tick, no flag.

The report (D19, D20, D21; app/desk/report.py): every chore end (completed after
Confirm, paused at Confirm, stopped at a failed step) calls `report(done)`, which
puts what was done on the card and sends exactly one text through `Texts`; a
ticket or bill with a deadline also gets one day-before text, held here and sent
from `tick` when the desk's clock reaches nine in the morning the day before. A
product gets none. Every time is read on the desk's clock, never the wall.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from app.desk.clock import Clock, VirtualClock
from app.desk.deadlines import REMINDED_KINDS, reminder_at, reminder_until
from app.desk.report import Reminder, chore_key, chore_name, event_key, new_chore_id, reminder_text, report_text
from app.desk.texts import FakeTexts, Texts
from app.eye import Frame, Identification, size_text

# D4, D5: the one clock that decides between the card and "Hold it closer".
IDENTIFY_SECONDS = 5
HOLD_IT_CLOSER = "Hold it closer"
# A spoken yes (D7): the whole utterance, nothing more.
_YES = re.compile(r"^\s*(yes|yeah|yep|yes please|confirm)\s*[.!]?\s*$", re.IGNORECASE)
# A bare yes to "Is this the 32 oz?" (D8): the affirmation alone, nothing more.
_BARE_YES = re.compile(r"^\s*(yes|yeah|yep|it is|right|yes it is|that's right|correct)\s*[.!]?\s*$", re.IGNORECASE)


@dataclass
class Card:
    identified: dict[str, Any] | None = None  # {"kind", "fields"}: what the eye read
    done: str | None = None  # what the chore did, set at its end ("Paid citation …", "Ready to pay …, waiting for you", the failed step)
    deadline: str | None = None  # ISO date, or None (products have none)
    deadline_note: str | None = None  # how the deadline was found ("counted 21 days from the issue date")
    link: str | None = None  # the page the browser is on
    controls: list[str] = field(default_factory=list)  # e.g. ["Pay", "Contest"], ["Confirm"]
    question: str | None = None  # e.g. "Is this the 32 oz?"
    letter: str | None = None  # the contest letter, as pasted into the city's form
    notice: str | None = None  # "Hold it closer"
    failed_step: str | None = None  # the step's name when a chore stops
    call_to_pay: str | None = None  # a bill that could not be paid online: the phone number printed on it (D15)
    # The product chore (D16, D17): the stores that list the product, cheapest first, each
    # {"store", "price" ("$8.98", as its page shows it), "link"}; the stores marked "not found",
    # in store order; and the store the Buy control is on (the cheapest), while it shows.
    ranking: list[dict[str, str]] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    buy: str | None = None

    def document(self) -> dict[str, Any]:
        return asdict(self)


class Chore(Protocol):
    async def begin(self) -> None: ...
    async def tap(self, control: str) -> bool: ...
    async def say(self, text: str) -> bool: ...


class Eye(Protocol):
    def identify(self, frame: Frame) -> Identification: ...


@dataclass
class _Attempt:
    started: datetime
    deadline: datetime
    pending: tuple[datetime, Identification] | None = None


class GateClosed(RuntimeError):
    """A pay, buy or submit step was asked to run without Confirm."""


class Desk:
    def __init__(
        self,
        eye: Eye | None = None,
        chores: Callable[["Desk", Identification], Chore] | None = None,
        clock: Clock | None = None,
        texts: Texts | None = None,
        live: bool = False,
    ) -> None:
        self.eye = eye
        self.chores = chores
        # The app gives the desk its clock and its texts (create_app); a desk on its own
        # (a unit test) runs on a virtual clock that stands still and a fake that records.
        self.clock: Clock = clock if clock is not None else VirtualClock()
        self.texts: Texts = texts if texts is not None else FakeTexts()
        self.lock = asyncio.Lock()
        # Live mode: an ended chore offers Next; frames are ignored until it is tapped (one chore, one
        # text per thing held up, never a loop while the same thing stays in front of the camera).
        self.live = live
        self.reset()

    def reset(self) -> None:
        self.card = Card()
        self.frame: bytes | None = None
        self.frame_at: str | None = None
        self.eye_delay = 0.0  # test mode: seconds of virtual time the eye takes to answer
        self.identification: Identification | None = None
        self.chore: Chore | None = None
        self.chore_id: str | None = None  # this chore instance, in every idempotency key (risk-3)
        self._attempt: _Attempt | None = None
        self._paused: Callable[[], Awaitable[None]] | None = None
        self.confirmed = False
        self.reminders: list[Reminder] = []  # the day-before texts waiting on the clock (D20)
        self._reminded = False  # one day-before text per chore

    def chore_has_ended(self) -> bool:
        """A chore that stopped at a failed step, or completed after Confirm, holds the desk no longer.
        A chore paused at Confirm, or still working, does."""
        if self.chore is None:
            return True
        if getattr(self.chore, "stopped", False):
            return True
        return self.card.done is not None and self._paused is None

    def start_over(self) -> None:
        """A fresh card for the next thing; the day-before texts already scheduled stay on the clock."""
        reminders, reminded = self.reminders, self._reminded
        self.reset()
        self.reminders = reminders
        self._reminded = False
        del reminded

    def state(self) -> dict[str, Any]:
        return self.card.document()

    # --- the eye and the five-second clock -------------------------------------------

    async def take_frame(self, image: bytes, content_type: str, at: datetime) -> None:
        self.frame = image
        self.frame_at = at.isoformat()
        if self.identification is not None:
            return  # a thing is named; its chore holds the desk until Next (live) or a reset (tests)
        if self._attempt is None:
            self._attempt = _Attempt(started=at, deadline=at + timedelta(seconds=IDENTIFY_SECONDS))
        if self._attempt.pending is None:
            if self.eye is None:
                raise RuntimeError("the desk has no eye")
            answer = self.eye.identify(Frame(image=image, content_type=content_type))
            # The answer arrived when the clock says it did: live, a slow eye's own latency
            # counts against the five seconds; on the virtual clock (which never moves
            # during a call) the latency set for the scenario does.
            arrived = max(at + timedelta(seconds=self.eye_delay), self.clock.now())
            self._attempt.pending = (arrived, answer)
        await self.tick(max(at, self.clock.now()))

    async def tick(self, now: datetime) -> None:
        """The clock moved: a day-before text that has fallen due goes (D20); an answer
        that has arrived within five seconds names the thing; at five seconds with none,
        "Hold it closer". Nothing else happens here."""
        self._remind(now)
        attempt = self._attempt
        if attempt is None:
            return
        if attempt.pending is not None and attempt.pending[0] <= now:
            ready_at, answer = attempt.pending
            attempt.pending = None
            if ready_at <= attempt.deadline and answer.kind != "unknown":
                self._attempt = None
                await self._identified(answer)
                return
        if now >= attempt.deadline:
            self._attempt = None
            self.card.notice = HOLD_IT_CLOSER

    async def _identified(self, ident: Identification) -> None:
        self.identification = ident
        self.card.notice = None
        self.card.identified = {"kind": ident.kind, "fields": dict(ident.fields)}
        if ident.variant_question:
            self.card.question = ident.variant_question  # D8: no store is searched until it is answered
            return
        await self._begin()

    async def _begin(self) -> None:
        assert self.identification is not None
        if self.chores is None:
            raise RuntimeError("the desk has no hands")
        self.chore_id = new_chore_id()
        self.chore = self.chores(self, self.identification)
        await self.chore.begin()

    # --- the user's words and taps ------------------------------------------------------

    async def tap(self, control: str) -> bool:
        if control == "Next":
            if not (self.live and self.chore_has_ended()):
                return False
            self.start_over()
            return True
        if control == "Confirm" or control not in self.card.controls or self.chore is None:
            return False
        return await self.chore.tap(control)

    async def say(self, text: str) -> bool:
        if self._paused is not None:
            if _YES.match(text):
                return await self.confirm()
            return False
        if self.identification is not None and self.identification.kind == "product" and self.card.question:
            return await self._answer_variant(text)
        if self.chore is not None:
            return await self.chore.say(text)
        if self.live and self.identification is None and text.strip():
            # Live mode, for reach and robustness: a product typed instead of held up. The typed
            # words are the product's name; the chore then runs exactly as after the camera.
            self._attempt = None
            self.card.notice = None
            await self._identified(Identification(kind="product", fields={"name": text.strip(), "brand": None, "size": None}, confidence=1.0))
            return True
        return False

    async def _answer_variant(self, text: str) -> bool:
        ident = self.identification
        assert ident is not None
        guess = ident.fields.get("size_guess")
        words = text.strip().lower()
        # A size the user states wins over the guess (D8: a correction answers the
        # question); only a bare yes accepts the guess (risk-2).
        m = re.search(r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|oz|ounces?|ml|l|g|kg|lb|ct|count)?\b", words)
        if m:
            unit = m.group(2) or (str(guess).split(" ", 1)[1] if guess and " " in str(guess) else "oz")
            size = size_text(f"{m.group(1)} {unit}")
            if size is None:
                return False
        elif guess and _BARE_YES.match(words):
            size = guess
        else:
            return False
        ident.fields["size"] = size
        ident.fields.pop("size_guess", None)
        ident.variant_question = None
        self.card.identified = {"kind": ident.kind, "fields": dict(ident.fields)}
        self.card.question = None
        await self._begin()
        return True

    # --- the report ---------------------------------------------------------------------

    def report(self, done: str) -> None:
        """A chore has ended (completed, paused at Confirm, or stopped at a failed step):
        the card says what was done beside what was identified, the deadline and the
        link, and the phone gets exactly one text with the same and the deadline (D19).
        A ticket or bill with a deadline is also held for its day-before text (D20)."""
        card = self.card
        card.done = done
        ident = self.identification
        kind = ident.kind if ident is not None else "unknown"
        fields = ident.fields if ident is not None else {}
        chore = chore_key(kind, fields)
        if self.chore_id is None:
            self.chore_id = new_chore_id()
        chore_id = self.chore_id
        now = self.clock.now()
        self.texts.send(report_text(done, card.deadline, card.deadline_note), now.isoformat(), event_key(chore, chore_id, f"end:{done}"))
        if self.live and self.chore_has_ended():
            card.controls = ["Next"]
        name = chore_name(kind, fields)
        if self._reminded or kind not in REMINDED_KINDS or card.deadline is None or name is None:
            return  # D21: a product has no deadline and gets no second text
        at = reminder_at(card.deadline)
        if at <= now:
            return  # nine the day before has already passed: the end's own text named the deadline
        self._reminded = True
        self.reminders.append(
            Reminder(
                at=at,
                until=reminder_until(card.deadline),
                body=reminder_text(name, card.deadline),
                key=event_key(chore, chore_id, f"reminder:{card.deadline}"),
            )
        )

    def _remind(self, now: datetime) -> None:
        """Send every day-before text whose time the clock has reached, stamped with the clock's
        time, while it is still the day before: once the deadline day has begun the text would
        say a false "tomorrow", so it is dropped unsent (risk-2)."""
        reached = [r for r in self.reminders if r.at <= now]
        if not reached:
            return
        self.reminders = [r for r in self.reminders if r.at > now]
        for reminder in sorted(reached, key=lambda r: r.at):
            if now < reminder.until:
                self.texts.send(reminder.body, now.isoformat(), reminder.key)

    # --- the Confirm gate ---------------------------------------------------------------

    def pause_for_confirm(self, step: Callable[[], Awaitable[None]], waiting: str) -> None:
        """A chore stops before its pay, buy or submit step: Confirm is the only control,
        and the step waits here, for as long as it takes (D6). The pause is a chore end:
        the card and one text say what is waiting (D19)."""
        self._paused = step
        self.confirmed = False
        self.card.controls = ["Confirm"]
        self.report(waiting)

    @property
    def waiting_for_confirm(self) -> bool:
        return self._paused is not None

    async def confirm(self) -> bool:
        """The only way past the gate: a tap on Confirm or a spoken yes (D7)."""
        step = self._paused
        if step is None:
            return False
        self._paused = None
        self.card.controls = []
        self.confirmed = True
        try:
            await step()
        finally:
            self.confirmed = False
        return True

    def require_confirmed(self) -> None:
        if not self.confirmed:
            raise GateClosed("a pay, buy or submit step runs only after Confirm")
