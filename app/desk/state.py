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
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from app.eye import Frame, Identification, size_text

# D4, D5: the one clock that decides between the card and "Hold it closer".
IDENTIFY_SECONDS = 5
HOLD_IT_CLOSER = "Hold it closer"
# A spoken yes (D7): the whole utterance, nothing more.
_YES = re.compile(r"^\s*(yes|yeah|yep|yes please|confirm)\s*[.!]?\s*$", re.IGNORECASE)


@dataclass
class Card:
    identified: dict[str, Any] | None = None  # {"kind", "fields"}: what the eye read
    done: str | None = None  # what the chore did ("Paid citation …")
    deadline: str | None = None  # ISO date, or None (products have none)
    deadline_note: str | None = None  # how the deadline was found ("counted 21 days from the issue date")
    link: str | None = None  # the page the browser is on
    controls: list[str] = field(default_factory=list)  # e.g. ["Pay", "Contest"], ["Confirm"]
    question: str | None = None  # e.g. "Is this the 32 oz?"
    letter: str | None = None  # the contest letter, as pasted into the city's form
    notice: str | None = None  # "Hold it closer"
    failed_step: str | None = None  # the step's name when a chore stops

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
    def __init__(self, eye: Eye | None = None, chores: Callable[["Desk", Identification], Chore] | None = None) -> None:
        self.eye = eye
        self.chores = chores
        self.lock = asyncio.Lock()
        self.reset()

    def reset(self) -> None:
        self.card = Card()
        self.frame: bytes | None = None
        self.frame_at: str | None = None
        self.eye_delay = 0.0  # test mode: seconds of virtual time the eye takes to answer
        self.identification: Identification | None = None
        self.chore: Chore | None = None
        self._attempt: _Attempt | None = None
        self._paused: Callable[[], Awaitable[None]] | None = None
        self.confirmed = False

    def state(self) -> dict[str, Any]:
        return self.card.document()

    # --- the eye and the five-second clock -------------------------------------------

    async def take_frame(self, image: bytes, content_type: str, at: datetime) -> None:
        self.frame = image
        self.frame_at = at.isoformat()
        if self.identification is not None:
            return  # a thing is named; its chore holds the desk
        if self._attempt is None:
            self._attempt = _Attempt(started=at, deadline=at + timedelta(seconds=IDENTIFY_SECONDS))
        if self._attempt.pending is None:
            if self.eye is None:
                raise RuntimeError("the desk has no eye")
            answer = self.eye.identify(Frame(image=image, content_type=content_type))
            self._attempt.pending = (at + timedelta(seconds=self.eye_delay), answer)
        await self.tick(at)

    async def tick(self, now: datetime) -> None:
        """The clock moved: an answer that has arrived within five seconds names the
        thing; at five seconds with none, "Hold it closer". Nothing else happens here."""
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
        self.chore = self.chores(self, self.identification)
        await self.chore.begin()

    # --- the user's words and taps ------------------------------------------------------

    async def tap(self, control: str) -> bool:
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
        return False

    async def _answer_variant(self, text: str) -> bool:
        ident = self.identification
        assert ident is not None
        guess = ident.fields.get("size_guess")
        words = text.strip().lower()
        if guess and re.match(r"^(yes|yeah|yep|it is|right)\b", words):
            size = guess
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|oz|ounces?|ml|l|g|kg|lb|ct|count)?\b", words)
            if not m:
                return False
            unit = m.group(2) or (str(guess).split(" ", 1)[1] if guess and " " in str(guess) else "oz")
            size = size_text(f"{m.group(1)} {unit}")
            if size is None:
                return False
        ident.fields["size"] = size
        ident.fields.pop("size_guess", None)
        ident.variant_question = None
        self.card.identified = {"kind": ident.kind, "fields": dict(ident.fields)}
        self.card.question = None
        await self._begin()
        return True

    # --- the Confirm gate ---------------------------------------------------------------

    def pause_for_confirm(self, step: Callable[[], Awaitable[None]]) -> None:
        """A chore stops before its pay, buy or submit step: Confirm is the only control,
        and the step waits here, for as long as it takes (D6)."""
        self._paused = step
        self.confirmed = False
        self.card.controls = ["Confirm"]

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
