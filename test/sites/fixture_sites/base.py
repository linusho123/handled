from __future__ import annotations

import html
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response


class SiteError(ValueError):
    pass


def page(title: str, body: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title></head>"
        f"<body><h1>{html.escape(title)}</h1>{body}</body></html>",
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
