"""Texts to the user's phone: one interface, a fake that records in tests, and the
live senders chosen by the keys present at startup.

  FakeTexts      test mode only; records every text (GET /test/texts) and never
                 reaches the network.
  PhotonTexts    PHOTON_API_KEY + PHOTON_PROJECT_ID (PHOTON_AGENT_HANDLE optional:
                 the shared iMessage number, to pick its conversation). Photon's
                 shared iMessage line never sends first, so the user texts it once;
                 the sender finds that inbound message (listMessages, direction
                 received, platform imessage), keeps its space.id and receivedBy.id,
                 and sends every text as sendMessage into that space with senderId =
                 receivedBy.id and a stable idempotency key per chore event. With no
                 inbound message it logs that the handshake is missing and the text
                 falls through to the next sender.
  TwilioTexts    TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_FROM + TWILIO_TO.
  LoggedTexts    neither: the text is printed to the app's log, never sent.

Keys are read from the environment the app was started with (npm run app loads
.env through node's --env-file); the app never opens a key file itself, and no
sender logs a key, a header or a response body: only a status code.
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

PHOTON_API = "https://api.photon.codes/v1"
TWILIO_API = "https://api.twilio.com/2010-04-01"
HTTP_TIMEOUT_S = 10

# (method, url, headers, body) -> (status, body). The live senders' only door to the network.
Http = Callable[[str, str, dict[str, str], bytes | None], tuple[int, bytes]]
Log = Callable[[str], None]


def _log(line: str) -> None:
    print(f"handled texts: {line}", file=sys.stderr, flush=True)


def urllib_http(method: str, url: str, headers: dict[str, str], body: bytes | None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:  # noqa: S310 (fixed https hosts)
            return response.status, response.read()
    except urllib.error.HTTPError as err:
        return err.code, b""
    except (urllib.error.URLError, TimeoutError, OSError):
        return 0, b""


class Texts:
    name = "texts"

    def send(self, body: str, at: str, key: str | None = None) -> bool:
        """Send one text; True when this sender took it."""
        raise NotImplementedError

    def prepare(self) -> None:
        """Startup: say which sender is live (and, for Photon, look for the handshake)."""


class FakeTexts(Texts):
    name = "fake"

    def __init__(self, to: str = "+15555550123") -> None:
        self.to = to
        self.sent: list[dict[str, Any]] = []

    def send(self, body: str, at: str, key: str | None = None) -> bool:
        self.sent.append({"to": self.to, "body": body, "at": at, "key": key})
        return True

    def reset(self) -> None:
        self.sent = []


class LoggedTexts(Texts):
    """No sender configured: the text goes to the log, so the operator sees what would have gone."""

    name = "logged"

    def __init__(self, log: Log = _log) -> None:
        self.log = log

    def send(self, body: str, at: str, key: str | None = None) -> bool:
        self.log(f"not sent (no Photon or Twilio keys) at {at}: {body}")
        return True


class PhotonTexts(Texts):
    name = "photon"

    def __init__(self, api_key: str, project_id: str, agent_handle: str | None = None, http: Http = urllib_http, log: Log = _log) -> None:
        self._api_key = api_key
        self.project_id = project_id
        self.agent_handle = agent_handle or None
        self.http = http
        self.log = log
        self.space_id: str | None = None
        self.sender_id: str | None = None

    def _headers(self, key: str | None = None) -> dict[str, str]:
        # Photon's edge answers 403 to Python's default urllib User-Agent (seen 2026-10-18); name ourselves.
        headers = {"Authorization": f"Bearer {self._api_key}", "Accept": "application/json", "User-Agent": "handled/0.1"}
        if key is not None:
            headers["Content-Type"] = "application/json"
            headers["idempotency-key"] = key
        return headers

    def _url(self, path: str, query: dict[str, str | int] | None = None) -> str:
        url = f"{PHOTON_API}/projects/{urllib.parse.quote(self.project_id, safe='')}{path}"
        return f"{url}?{urllib.parse.urlencode(query)}" if query else url

    def handshake(self) -> bool:
        """Find the user's inbound iMessage and keep its conversation. True once found."""
        if self.space_id and self.sender_id:
            return True
        query = {"direction": "received", "platform": "imessage", "order": "desc", "orderBy": "created_at", "pageSize": 50}
        status, body = self.http("GET", self._url("/messages", query), self._headers(), None)
        if status != 200:
            self.log(f"photon: listing received messages answered {status}; the handshake is missing")
            return False
        try:
            items = json.loads(body).get("items") or []
        except (ValueError, AttributeError):
            items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            space, line = item.get("space") or {}, item.get("receivedBy") or {}
            if not (isinstance(space, dict) and isinstance(line, dict) and space.get("id") and line.get("id")):
                continue
            if self.agent_handle and line.get("handle") != self.agent_handle:
                continue
            self.space_id, self.sender_id = str(space["id"]), str(line["id"])
            self.log("photon: found the user's message; texts reply into that conversation")
            return True
        self.log("photon: no received iMessage yet; the handshake is missing (text the shared line once from the phone)")
        return False

    def prepare(self) -> None:
        self.handshake()

    def send(self, body: str, at: str, key: str | None = None) -> bool:
        if not self.handshake():
            return False
        payload = {"spaceId": self.space_id, "senderId": self.sender_id, "content": {"type": "text", "format": "plain", "text": body}}
        status, _ = self.http("POST", self._url("/messages"), self._headers(key or "handled-unkeyed"), json.dumps(payload).encode("utf-8"))
        if 200 <= status < 300:
            self.log(f"photon: sent ({status})")
            return True
        self.log(f"photon: sendMessage answered {status}")
        return False


class TwilioTexts(Texts):
    name = "twilio"

    def __init__(self, account_sid: str, auth_token: str, sender: str, to: str, http: Http = urllib_http, log: Log = _log) -> None:
        self.account_sid = account_sid
        self._auth_token = auth_token
        self.sender = sender
        self.to = to
        self.http = http
        self.log = log

    def send(self, body: str, at: str, key: str | None = None) -> bool:
        auth = base64.b64encode(f"{self.account_sid}:{self._auth_token}".encode()).decode()
        headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}
        url = f"{TWILIO_API}/Accounts/{urllib.parse.quote(self.account_sid, safe='')}/Messages.json"
        form = urllib.parse.urlencode({"From": self.sender, "To": self.to, "Body": body}).encode()
        status, _ = self.http("POST", url, headers, form)
        if 200 <= status < 300:
            self.log(f"twilio: sent ({status})")
            return True
        self.log(f"twilio: answered {status}")
        return False


class ChainTexts(Texts):
    """The live senders in order; a text goes through the first that takes it, else the log."""

    name = "chain"

    def __init__(self, senders: list[Texts], fallback: Texts | None = None, log: Log = _log) -> None:
        self.senders = senders
        self.fallback = fallback or LoggedTexts(log)
        self.log = log

    def prepare(self) -> None:
        names = [s.name for s in self.senders] or ["none"]
        self.log(f"senders configured: {', '.join(names)} (then the log)")
        for sender in self.senders:
            sender.prepare()

    def send(self, body: str, at: str, key: str | None = None) -> bool:
        for sender in self.senders:
            if sender.send(body, at, key):
                return True
        return self.fallback.send(body, at, key)


def texts_from_env(env: Mapping[str, str], http: Http = urllib_http, log: Log = _log) -> ChainTexts:
    """Photon if its keys are present, then Twilio if its are, then the log."""
    senders: list[Texts] = []
    if env.get("PHOTON_API_KEY") and env.get("PHOTON_PROJECT_ID"):
        senders.append(PhotonTexts(env["PHOTON_API_KEY"], env["PHOTON_PROJECT_ID"], env.get("PHOTON_AGENT_HANDLE"), http=http, log=log))
    if all(env.get(k) for k in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM", "TWILIO_TO")):
        senders.append(TwilioTexts(env["TWILIO_ACCOUNT_SID"], env["TWILIO_AUTH_TOKEN"], env["TWILIO_FROM"], env["TWILIO_TO"], http=http, log=log))
    return ChainTexts(senders, LoggedTexts(log), log)
