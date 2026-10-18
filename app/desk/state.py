"""The desk's state: one JSON document, the card as the page renders it.

GET /desk returns exactly this document. After a reset every field is empty:
nothing identified, nothing done, no deadline, no link, no controls, no
question, no failed step. Later phases fill it; nothing here pre-seeds it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Card:
    identified: dict[str, Any] | None = None  # the kind and the fields the eye read
    done: str | None = None  # what the chore did ("Paid citation …")
    deadline: str | None = None  # ISO date, or None (products have none)
    link: str | None = None  # the page the browser is on
    controls: list[str] = field(default_factory=list)  # e.g. ["Pay", "Contest"], ["Confirm"]
    question: str | None = None  # e.g. "Is this the 32 oz?"
    failed_step: str | None = None  # the step's name when a chore stops

    def document(self) -> dict[str, Any]:
        return asdict(self)


class Desk:
    """The card, the latest frame, and (from P1) the Confirm gate."""

    def __init__(self) -> None:
        self.card = Card()
        self.frame: bytes | None = None
        self.frame_at: str | None = None

    def reset(self) -> None:
        self.card = Card()
        self.frame = None
        self.frame_at = None

    def state(self) -> dict[str, Any]:
        return self.card.document()

    def take_frame(self, image: bytes, at: str) -> None:
        # The eye that reads it arrives in P1; until then a frame is held, not identified.
        self.frame = image
        self.frame_at = at

    def waiting_for_confirm(self) -> bool:
        # No chore exists before P1, so nothing ever waits at the gate.
        return False
