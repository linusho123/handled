"""Record the eye's cassettes once, against live Gemini (BUILD-PLAN.md, P1).

  node --env-file=.env scripts/py.mjs scripts/record-cassettes.py

GEMINI_API_KEY comes from the environment (node's --env-file loads .env); this
script never prints, logs or stores it. It first confirms the model id against
the models list (printing the Flash ids it finds, never anything else from the
account), then records one identify cassette per fixture image (and a variant
cassette for a product whose size the frame hides) and the contest
letter for the spoken reason the ticket scenarios use. A cassette already on
disk is kept, not re-recorded. Output: the model id, then each cassette's file
name and byte count.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.eye import GEMINI_MODEL, Frame, GeminiEye  # noqa: E402
from app.eye.cassette import Cassette  # noqa: E402

IMAGES = ROOT / "test" / "fixtures" / "images"
# The reason the ticket scenarios speak (features/ticket.feature, D12; D7 "Saying yes").
REASONS = ["the meter was broken, I put in two dollars and it never started"]


def flash_models(client) -> list[str]:
    names = []
    for model in client.models.list():
        name = (model.name or "").removeprefix("models/")
        if "flash" in name and "generateContent" in (model.supported_actions or []):
            names.append(name)
    return sorted(names)


def retried(call, attempts: int = 4):
    """A transient server error (overloaded, 5xx) is tried again after a pause."""
    import time

    for attempt in range(attempts):
        try:
            return call()
        except Exception as err:
            transient = type(err).__name__ == "ServerError" or getattr(err, "code", None) == 429
            if not transient or attempt == attempts - 1:
                raise
            time.sleep(15 * (attempt + 1))
    raise AssertionError("unreachable")


def main() -> int:
    os.environ["HANDLED_RECORD"] = "1"
    eye = GeminiEye(Cassette(record=True))
    try:
        available = flash_models(eye._live_client())
    except Exception as err:  # never echo the request: print the error's type only
        print(f"models list failed: {type(err).__name__}", file=sys.stderr)
        return 1
    print("flash models:", ", ".join(available))
    if GEMINI_MODEL not in available:
        print(f"{GEMINI_MODEL} is not in the models list; set GEMINI_MODEL in app/eye/__init__.py to one of the above", file=sys.stderr)
        return 3
    print("model:", GEMINI_MODEL)

    written: list[Path] = []
    ticket = None
    for image in sorted(IMAGES.glob("*.png")):
        frame = Frame(image=image.read_bytes(), content_type="image/png")
        path = eye.cassette.path("identify", eye.identify_request(frame))
        try:
            ident = retried(lambda: eye.identify(frame))
        except Exception as err:
            print(f"{image.name}: {type(err).__name__} {getattr(err, 'code', '')} {getattr(err, 'status', '')}", file=sys.stderr)
            return 1
        written.append(path)
        if ident.kind == "product" and ident.fields.get("size") is None:
            written.append(eye.cassette.path("variant", eye.variant_request(frame, ident.fields["name"])))
        if image.name == "la-ticket.png":
            ticket = ident.fields
    if ticket is None:
        print("la-ticket.png was not identified as a ticket; no letter recorded", file=sys.stderr)
        return 1
    for reason in REASONS:
        written.append(eye.cassette.path("letter", eye.letter_request(ticket, reason)))
        try:
            retried(lambda: eye.write_letter(ticket, reason))
        except Exception as err:
            print(f"letter: {type(err).__name__} {getattr(err, 'code', '')} {getattr(err, 'status', '')}", file=sys.stderr)
            return 1
    for path in written:
        print(f"{path.name} {path.stat().st_size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
