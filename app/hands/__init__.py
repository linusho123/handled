"""The hands: a Playwright Chromium the user can watch (headless in tests).

P0 starts the browser and reads back what it shows; the chores (TicketChore,
BillChore, ProductChore) and the SiteMap arrive with their phases. In test mode
(HANDLED_SITES=fixtures) every request the browser makes is held to loopback,
where the fixture sites live: anything else is aborted, never fetched.
"""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Route, async_playwright

# Every form control the page shows, by name (else id), with the value the DOM holds now.
_READ_FIELDS = """() => {
  const out = {};
  for (const el of document.querySelectorAll('input, textarea, select')) {
    if (el.type === 'hidden' || el.type === 'submit' || el.type === 'button') continue;
    const key = el.name || el.id;
    if (!key) continue;
    out[key] = (el.type === 'checkbox' || el.type === 'radio') ? (el.checked ? el.value : '') : el.value;
  }
  return out;
}"""


def _loopback(url: str) -> bool:
    parts = urlsplit(url)
    if parts.scheme in ("about", "data", "blob"):
        return True
    host = parts.hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class Hands:
    def __init__(self, headless: bool = True, loopback_only: bool = True) -> None:
        self.headless = headless
        self.loopback_only = loopback_only
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    async def start(self) -> None:
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-background-networking", "--disable-component-update", "--no-first-run"],
        )
        await self._new_context()

    async def _new_context(self) -> None:
        assert self._browser is not None
        self._context = await self._browser.new_context()
        if self.loopback_only:
            await self._context.route("**/*", self._hold_to_loopback)

    @staticmethod
    async def _hold_to_loopback(route: Route) -> None:
        if _loopback(route.request.url):
            await route.continue_()
        else:
            await route.abort("blockedbyclient")

    async def stop(self) -> None:
        if self._browser is not None:
            await self._browser.close()
        if self._pw is not None:
            await self._pw.stop()
        self._browser = self._context = self._pw = None

    async def reset(self) -> None:
        """Every tab closed: a fresh context, so no cookie or page carries over."""
        if self._context is not None:
            await self._context.close()
        await self._new_context()

    @property
    def pages(self) -> list[Page]:
        return list(self._context.pages) if self._context is not None else []

    async def open(self, url: str) -> Page:
        """A new tab on url (the chores' first step; P0's unit tests drive it directly)."""
        assert self._context is not None, "the hands are not started"
        page = await self._context.new_page()
        await page.goto(url)
        return page

    async def view(self) -> dict[str, Any]:
        """What the browser shows, read from Playwright: the active (last opened) tab's
        url, title and filled fields, and every open tab. No tab: all empty."""
        pages = self.pages
        tabs = [{"url": p.url, "title": await p.title()} for p in pages]
        if not pages:
            return {"url": None, "title": None, "fields": {}, "tabs": []}
        active = pages[-1]
        return {"url": active.url, "title": await active.title(), "fields": await active.evaluate(_READ_FIELDS), "tabs": tabs}
