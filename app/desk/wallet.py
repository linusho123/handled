"""The card on file and the shipping address on file: the test Visa, in test mode and at
the demo (BUILD-PLAN.md; D25), and the address a store's checkout is filled with (D18)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CardOnFile:
    name: str
    number: str
    expiry: str
    cvc: str


@dataclass(frozen=True)
class ShipTo:
    name: str
    street: str
    city: str
    state: str
    zip: str


CARD_ON_FILE = CardOnFile(name="Handled Test", number="4242 4242 4242 4242", expiry="12/30", cvc="123")

# A placeholder address on file: the demo stops at Confirm before any order is placed (D25).
SHIP_TO = ShipTo(name="Handled Test", street="123 Main St", city="Los Angeles", state="CA", zip="90012")
