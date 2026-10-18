"""The eye: a frame in, an identification out (built in P1: GeminiEye behind a Cassette).

P0 holds only the shapes and the model id.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# The Gemini model the eye calls. Recorded here from the Taken plan; P1 confirms
# it against the models list (P0 makes no network call) and records the
# cassettes with it.
GEMINI_MODEL = "gemini-3.8-flash"

Kind = Literal["ticket", "bill", "product", "unknown"]


@dataclass(frozen=True)
class Frame:
    image: bytes  # JPEG from the page's getUserMedia capture, or a fixture PNG
    content_type: str


@dataclass
class Identification:
    kind: Kind
    fields: dict[str, Any] = field(default_factory=dict)
    variant_question: str | None = None
    confidence: float = 0.0
