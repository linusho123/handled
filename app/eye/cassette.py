"""Record-and-replay for every model call (BUILD-PLAN.md, "No live calls in tests").

A request is a JSON-able dict that names everything the answer depends on (the
model id, the prompt, the image's SHA-256, the spoken reason), never the key.
Its hash is the cassette's name. A cassette holds the request hash and the
response body (the model's text), nothing else. Replay is the default: a
request with no cassette raises CassetteMissing, loudly, and never reaches the
network. HANDLED_RECORD=1 records: a request with no cassette is answered live
once and written to test/cassettes/.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

CASSETTES = Path(__file__).resolve().parents[2] / "test" / "cassettes"


class CassetteMissing(RuntimeError):
    pass


def request_hash(request: dict[str, Any]) -> str:
    canonical = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Cassette:
    def __init__(self, directory: Path = CASSETTES, record: bool | None = None) -> None:
        self.directory = directory
        self.record = os.environ.get("HANDLED_RECORD") == "1" if record is None else record

    def path(self, kind: str, request: dict[str, Any]) -> Path:
        return self.directory / f"{kind}-{request_hash(request)[:16]}.json"

    def play(self, kind: str, request: dict[str, Any], live: Callable[[], str]) -> str:
        """The stored response for this request; recorded first under HANDLED_RECORD=1."""
        path = self.path(kind, request)
        key = request_hash(request)
        if path.exists():
            stored = json.loads(path.read_text(encoding="utf-8"))
            if stored.get("request_hash") != key:
                raise CassetteMissing(f"{path.name} holds request {stored.get('request_hash')!r}, not {key}")
            return str(stored["response"])
        if not self.record:
            raise CassetteMissing(
                f"no cassette {path.name} for this {kind} request (model {request.get('model')!r}); "
                "the fast lane never calls a model: record it once with HANDLED_RECORD=1 (scripts/record-cassettes.py)"
            )
        response = live()
        self.directory.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"request_hash": key, "response": response}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(path)
        return response
