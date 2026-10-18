"""The card on file: the test Visa, in test mode and at the demo (BUILD-PLAN.md; D25)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CardOnFile:
    name: str
    number: str
    expiry: str
    cvc: str


CARD_ON_FILE = CardOnFile(name="Handled Test", number="4242 4242 4242 4242", expiry="12/30", cvc="123")
