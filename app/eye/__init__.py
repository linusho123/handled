"""The eye: a frame in, an identification out; and the contest letter from a spoken reason.

GeminiEye calls Gemini through one Cassette (app/eye/cassette.py): tests replay
recorded answers and never reach the network; HANDLED_RECORD=1 records them
once. The eye only reads; the five-second clock belongs to the desk (D4, D5).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

from app.eye.cassette import Cassette, CassetteMissing

# The Gemini model the eye calls, confirmed against the models list when the
# cassettes were recorded (scripts/record-cassettes.py, 2026-10-18).
GEMINI_MODEL = "gemini-3.8-flash"
# Live mode only: when the model answers 503 UNAVAILABLE or 429 (high demand), the next model in this
# list is tried at once, without waiting (the P1 guard forbids real-time waits in app/). Confirmed
# against the key's models list at the demo integration, 2026-10-18. Cassettes replay regardless.
GEMINI_FALLBACKS = ("gemini-3.1-flash-lite", "gemini-flash-lite-latest", "gemini-3.5-flash")
# Live mode's first choice. Timed at the demo integration (2026-10-18, the fixture ticket, JSON answer):
# gemini-3.8-flash 153 s, 3.7-flash 17 s, 3.5-flash 7 s, 3.5-flash-lite 1.1 s, 3.1-flash-lite 1.4 s.
# The five-second rule (D4, D5) leaves only the lite models. Cassettes were recorded with GEMINI_MODEL
# and keep replaying under it; recording (HANDLED_RECORD=1) still uses GEMINI_MODEL so the request
# hash names the model that answered. HANDLED_LIVE_MODEL overrides the live choice.
LIVE_MODEL = "gemini-3.5-flash-lite"

Kind = Literal["ticket", "bill", "product", "unknown"]

# Bump when a prompt changes: every cassette recorded under the old prompt then misses, loudly.
PROMPT_VERSION = "p1"

IDENTIFY_PROMPT = """You are the eye of Handled. The image is one webcam frame of something a person holds up to a laptop.
Decide what it is and read its printed fields. Answer with one JSON object and nothing else:
{"kind": "ticket" | "bill" | "product" | "unknown", "legible": true | false, "fields": {...}, "size_visible": true | false, "size_guess": string | null}

kind "ticket": a parking citation. fields: city (the issuing city, e.g. "Los Angeles"), citation (the citation number, digits only), plate (the license plate, uppercase, no spaces), issued (the issue date, YYYY-MM-DD), due (the printed due date, YYYY-MM-DD, or null when no due date is printed), amount (the amount due, digits with a decimal point, e.g. "73.00"), violation.
kind "bill": a bill or letter with an amount due. fields: biller (the biller's short name as printed, e.g. "LADWP"), account (the account number, digits only), amount (e.g. "148.22"), due (YYYY-MM-DD), phone (the phone number printed for questions or payment, as printed).
kind "product": a retail product. fields: name (brand, product line and type, e.g. "Heinz Tomato ketchup"), brand, size (the size as printed, e.g. "12 oz", or null when the size cannot be read in this frame).
size_visible: for a product, whether its size can be read in this frame. size_guess: for a product whose size cannot be read, the size of this product you judge most likely from the container's shape and proportions (e.g. "12 oz"), else null.
legible: true only when every field listed for that kind can be read with certainty in this frame (for a product: its name; the size may be hidden). Never guess a digit: if any digit of a number or a date is blurred, smeared, too small or cut off, legible is false.
kind "unknown": anything else, or nothing at all, with fields {}."""

VARIANT_PROMPT = """The image is one webcam frame of {name} held up to a laptop. Its size cannot be fully read: part of the size line is hidden.
Which size is this most likely? First list the sizes {name} is actually sold in. Then pick the one this frame most likely shows: any characters of the size line that do show (a leading digit, a unit) rule out every size that does not begin with them, and the container's proportions decide among the rest.
Answer with one JSON object and nothing else: {{"sizes": [string, ...], "likely": string}}, each size written like "12 oz"."""

LETTER_PROMPT = """Write the statement a driver submits to contest parking citation {citation}, issued in {city} to license plate {plate}.
The driver's reason, in their own words: "{reason}"
Keep every fact the driver gave and add none. Write in the first person as the driver. One paragraph of plain text: no line breaks, no greeting line, no signature, under 120 words."""

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


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


UNKNOWN = Identification(kind="unknown")


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def _date(value: Any) -> str | None:
    text = _text(value)
    if text is None or not _ISO.match(text):
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        return None


def _amount(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    text = text.replace("$", "").replace(",", "").strip()
    return text if re.fullmatch(r"\d+\.\d{2}", text) else None


def _digits(value: Any) -> str | None:
    text = _text(value)
    return text if text is not None and re.fullmatch(r"\d{6,}", text.replace(" ", "")) else None


def size_text(value: Any) -> str | None:
    """"32 FL OZ", "32fl oz", "32 oz." → "32 oz"; anything without a number → None."""
    text = _text(value)
    if text is None:
        return None
    m = re.match(r"^(\d+(?:\.\d+)?)\s*(fl\.?\s*oz|oz|ounces?|ml|l|g|kg|lb|ct|count)\.?$", text, re.IGNORECASE)
    if not m:
        return None
    unit = m.group(2).lower().replace(".", "")
    unit = "oz" if unit.replace(" ", "") in ("floz", "oz", "ounce", "ounces") else unit
    return f"{m.group(1)} {unit}"


def parse_identification(text: str) -> Identification:
    """The model's JSON answer, checked: a kind whose required fields are not all
    legible is unknown, never a half-read thing."""
    try:
        data = json.loads(text)
    except ValueError:
        return UNKNOWN
    if not isinstance(data, dict) or data.get("legible") is not True:
        return UNKNOWN
    raw = data.get("fields") if isinstance(data.get("fields"), dict) else {}
    kind = data.get("kind")
    if kind == "ticket":
        fields = {
            "city": _text(raw.get("city")),
            "citation": _digits(raw.get("citation")),
            "plate": (_text(raw.get("plate")) or "").replace(" ", "").upper() or None,
            "issued": _date(raw.get("issued")),
            "due": _date(raw.get("due")),
            "amount": _amount(raw.get("amount")),
            "violation": _text(raw.get("violation")),
        }
        if not all(fields[k] for k in ("city", "citation", "plate", "issued")):
            return UNKNOWN
        return Identification(kind="ticket", fields=fields, confidence=1.0)
    if kind == "bill":
        fields = {
            "biller": _text(raw.get("biller")),
            "account": _digits(raw.get("account")),
            "amount": _amount(raw.get("amount")),
            "due": _date(raw.get("due")),
            "phone": _text(raw.get("phone")),
        }
        if not all(fields[k] for k in ("biller", "account", "amount", "due")):
            return UNKNOWN
        return Identification(kind="bill", fields=fields, confidence=1.0)
    if kind == "product":
        name = _text(raw.get("name"))
        if not name:
            return UNKNOWN
        size = size_text(raw.get("size")) if data.get("size_visible") is not False else None
        fields = {"name": name, "brand": _text(raw.get("brand")), "size": size}
        # A product whose size the frame does not settle gets the variant question (D8);
        # GeminiEye.identify asks it in its own call.
        question = None if size is not None else "What size is this?"
        return Identification(kind="product", fields=fields, variant_question=question, confidence=1.0)
    return UNKNOWN


def one_paragraph(text: str) -> str:
    return " ".join(text.split())


class GeminiEye:
    """Gemini vision behind the cassette. The client is made only when a live call is recorded."""

    def __init__(self, cassette: Cassette | None = None, model: str = GEMINI_MODEL) -> None:
        self.cassette = cassette or Cassette()
        self.model = model
        self._client: Any = None

    def _live_client(self) -> Any:
        if self._client is None:
            from google import genai

            key = os.environ.get("GEMINI_API_KEY")
            if not key:
                raise CassetteMissing("recording needs GEMINI_API_KEY in the environment (loaded from .env, never printed)")
            self._client = genai.Client(api_key=key)
        return self._client

    def _generate(self, parts: list[Any], json_answer: bool) -> str:
        from google.genai import types

        from google.genai import errors

        config = types.GenerateContentConfig(response_mime_type="application/json") if json_answer else None
        last: Exception | None = None
        recording = os.environ.get("HANDLED_RECORD") == "1"
        first = self.model if recording else os.environ.get("HANDLED_LIVE_MODEL") or LIVE_MODEL
        for model in (first, *(m for m in GEMINI_FALLBACKS if m != first)):
            try:
                response = self._live_client().models.generate_content(model=model, contents=parts, config=config)
                return response.text or ""
            except errors.APIError as err:  # 503 high demand, 429 quota: the next model, at once
                if getattr(err, "code", None) not in (429, 503):
                    raise
                last = err
        assert last is not None
        raise last

    def identify_request(self, frame: Frame) -> dict[str, Any]:
        return {
            "call": "identify",
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "prompt": IDENTIFY_PROMPT,
            "image_sha256": hashlib.sha256(frame.image).hexdigest(),
        }

    def identify(self, frame: Frame) -> Identification:
        def live() -> str:
            from google.genai import types

            return self._generate([types.Part.from_bytes(data=frame.image, mime_type=frame.content_type), IDENTIFY_PROMPT], json_answer=True)

        ident = parse_identification(self.cassette.play("identify", self.identify_request(frame), live))
        if ident.kind == "product" and ident.fields.get("size") is None:
            guess = self.likely_size(frame, ident.fields["name"])
            if guess is not None:
                ident.fields["size_guess"] = guess
                ident.variant_question = f"Is this the {guess}?"
        return ident

    def variant_request(self, frame: Frame, name: str) -> dict[str, Any]:
        return {
            "call": "variant",
            "model": self.model,
            "prompt_version": PROMPT_VERSION,
            "prompt": VARIANT_PROMPT.format(name=name),
            "image_sha256": hashlib.sha256(frame.image).hexdigest(),
        }

    def likely_size(self, frame: Frame, name: str) -> str | None:
        """The size the variant question offers (D8): its own call, so the identify answer stays one read."""
        request = self.variant_request(frame, name)

        def live() -> str:
            from google.genai import types

            return self._generate([types.Part.from_bytes(data=frame.image, mime_type=frame.content_type), request["prompt"]], json_answer=True)

        try:
            data = json.loads(self.cassette.play("variant", request, live))
        except ValueError:
            return None
        return size_text(data.get("likely")) if isinstance(data, dict) else None

    def letter_request(self, ticket: dict[str, Any], reason: str) -> dict[str, Any]:
        prompt = LETTER_PROMPT.format(citation=ticket.get("citation"), city=ticket.get("city"), plate=ticket.get("plate"), reason=reason.strip())
        return {"call": "letter", "model": self.model, "prompt_version": PROMPT_VERSION, "prompt": prompt}

    def write_letter(self, ticket: dict[str, Any], reason: str) -> str:
        """A one-paragraph contest letter from the spoken reason (D12)."""
        request = self.letter_request(ticket, reason)
        letter = one_paragraph(self.cassette.play("letter", request, lambda: self._generate([request["prompt"]], json_answer=False)))
        if not letter:
            raise ValueError("the letter came back empty")
        return letter


__all__ = ["Cassette", "CassetteMissing", "Frame", "GEMINI_FALLBACKS", "GEMINI_MODEL", "LIVE_MODEL", "GeminiEye", "Identification", "Kind", "parse_identification", "size_text"]
