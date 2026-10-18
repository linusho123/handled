"""Texts to the user's phone: one interface, a fake that records in tests.

Photon (then Twilio) is wired at the demo integration (PD); the fake never
reaches the network.
"""

from __future__ import annotations

from typing import Any


class Texts:
    def send(self, body: str, at: str) -> None:
        raise NotImplementedError


class FakeTexts(Texts):
    def __init__(self, to: str = "+15555550123") -> None:
        self.to = to
        self.sent: list[dict[str, Any]] = []

    def send(self, body: str, at: str) -> None:
        self.sent.append({"to": self.to, "body": body, "at": at})

    def reset(self) -> None:
        self.sent = []
