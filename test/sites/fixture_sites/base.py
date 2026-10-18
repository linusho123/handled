from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response


class SiteError(ValueError):
    pass


# The look of a fixture page. A site may pass a brand header (the city's, a store's) so the
# demo's browser reads like the real page; every styled page says it is a fixture in its footer.
STYLE = (
    "<style>body{margin:0;font:16px/1.5 -apple-system,Helvetica,Arial,sans-serif;color:#1f2a37;background:#f4f6f9}"
    ".brand{background:var(--brand,#0b3d91);color:#fff;padding:14px 28px;font-size:22px;font-weight:600;letter-spacing:.2px}"
    ".brand small{display:block;font-size:13px;font-weight:400;opacity:.85}"
    "main{max-width:760px;margin:28px auto;background:#fff;padding:28px 32px;border-radius:8px;box-shadow:0 1px 4px rgba(0,0,0,.08)}"
    "h1{font-size:22px;margin:0 0 18px}label{display:block;margin:10px 0 4px}input,textarea{font:inherit;padding:8px;border:1px solid #c6ccd4;border-radius:4px;width:100%;max-width:420px}"
    "button,a.button{display:inline-block;margin:14px 8px 0 0;padding:10px 18px;background:var(--brand,#0b3d91);color:#fff;border:0;border-radius:4px;font:inherit;text-decoration:none;cursor:pointer}"
    "dl{display:grid;grid-template-columns:160px 1fr;gap:6px 12px}dt{color:#5b6472}.error{color:#b00020}"
    "footer{max-width:760px;margin:0 auto 28px;color:#7a8290;font-size:13px;padding:0 32px}</style>"
)


def page(title: str, body: str, status: int = 200, brand: str = "", color: str = "") -> HTMLResponse:
    """A fixture page. `brand` adds a header bar styled after the real site (demo); the footer
    says it is a fixture either way, so nobody mistakes it for the real page."""
    style = f" style='--brand:{html.escape(color)}'" if color else ""
    header = f"<div class='brand'{style}>{brand}</div>" if brand else ""
    footer = "<footer>Handled fixture site: a replica for tests and the demo, not the real page.</footer>" if brand else ""
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title>{STYLE}</head>"
        f"<body>{header}<main><h1>{html.escape(title)}</h1>{body}</main>{footer}</body></html>",
        status_code=status,
    )


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def last4(card_number: str) -> str:
    digits = "".join(c for c in card_number if c.isdigit())
    return digits[-4:]


class Site:
    """One fixture site: its faults, its ledger, its routes."""

    name: str = ""
    faults: frozenset[str] = frozenset()

    def __init__(self) -> None:
        self.fault: str | None = None
        self._ledger: list[dict[str, Any]] = []

    @property
    def ledger(self) -> list[dict[str, Any]]:
        return [dict(entry) for entry in self._ledger]

    def record(self, entry: dict[str, Any]) -> None:
        """Called only from the site's own submit / pay / order route handlers."""
        self._ledger.append(entry)

    def reset(self) -> None:
        self.fault = None
        self._ledger = []

    def set_fault(self, fault: str | None) -> None:
        if fault is not None and (not isinstance(fault, str) or fault not in self.faults):
            known = ", ".join(sorted(self.faults)) or "none"
            raise SiteError(f"{self.name} has no fault {fault!r}; its faults are {known}")
        self.fault = fault

    def describe(self) -> dict[str, Any]:
        return {"site": self.name, "fault": self.fault}

    def fault_response(self, request: Request) -> Response | None:
        """The answer a fault gives instead of the page: `down` answers nothing
        (an empty 503, a blank tab); `login` sends every page to the login wall."""
        if self.fault == "down":
            return Response(content=b"", status_code=503)
        if self.fault == "login" and not request.url.path.endswith("/login"):
            return RedirectResponse(f"/sites/{self.name}/login", status_code=303)
        return None

    def login_page(self) -> HTMLResponse:
        # A login wall: a username and a password. Posting it never signs anyone in.
        return page(
            f"{self.title} - Sign in",
            f"<form method='post' action='/sites/{self.name}/login'>"
            "<label>Username <input name='username'></label>"
            "<label>Password <input name='password' type='password'></label>"
            "<button type='submit'>Sign in</button></form>",
        )

    title: str = ""

    def router(self) -> APIRouter:
        raise NotImplementedError
