"""The HTTP server: the page, the desk's endpoints, and in test mode the /test/* endpoints
and the fixture sites (BUILD-PLAN.md, "Architecture").

Every /test/* endpoint reports what the app holds; none pre-seeds anything.
"""

from __future__ import annotations

import io
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from PIL import Image, UnidentifiedImageError

from app.desk import Clock, Desk, FakeTexts, VirtualClock
from app.hands import Hands

PAGE = Path(__file__).with_name("page.html")


def _image(body: bytes) -> bytes:
    """The frame, if it is a PNG or JPEG image; else a 400."""
    try:
        with Image.open(io.BytesIO(body)) as img:
            if img.format not in ("PNG", "JPEG"):
                raise HTTPException(400, f"a frame is a PNG or JPEG image, not {img.format}")
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as err:
        raise HTTPException(400, "a frame is a PNG or JPEG image") from err
    return body


async def _json(request: Request) -> dict[str, Any]:
    body = await request.body()
    if not body:
        return {}
    try:
        data = await request.json()
    except ValueError as err:
        raise HTTPException(400, "the body is not JSON") from err
    if not isinstance(data, dict):
        raise HTTPException(400, "the body is a JSON object")
    return data


def create_app(
    *,
    clock: Clock,
    desk: Desk,
    hands: Hands,
    texts: FakeTexts | None = None,
    sites: Any = None,
    test_mode: bool = False,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await hands.start()
        try:
            yield
        finally:
            await hands.stop()

    api = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    now = lambda: clock.now().isoformat()  # noqa: E731

    @api.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE.read_text(encoding="utf-8")

    @api.get("/desk")
    def get_desk() -> dict[str, Any]:
        return desk.state()

    @api.post("/frame")
    async def frame(request: Request) -> dict[str, Any]:
        desk.take_frame(_image(await request.body()), now())
        return {"accepted": True, "at": desk.frame_at}

    @api.post("/confirm")
    def confirm() -> JSONResponse:
        if not desk.waiting_for_confirm():
            return JSONResponse({"error": "nothing is waiting for Confirm"}, status_code=409)
        raise HTTPException(500, "unreachable before P1")

    @api.post("/say")
    def say() -> JSONResponse:
        return JSONResponse({"error": "speech is not built yet (P1)"}, status_code=501)

    if test_mode:
        assert isinstance(clock, VirtualClock) and texts is not None and sites is not None
        api.include_router(_test_router(clock, desk, hands, texts, sites))
        api.include_router(sites.router())
    return api


def _test_router(clock: VirtualClock, desk: Desk, hands: Hands, texts: FakeTexts, sites: Any) -> APIRouter:
    from fixture_sites import SiteError

    t = APIRouter(prefix="/test")

    @t.post("/reset")
    async def reset(request: Request) -> dict[str, str]:
        data = await _json(request)
        start = data.get("start")
        if start is None:
            clock.reset()
        else:
            try:
                clock.reset(datetime.fromisoformat(str(start)))
            except ValueError as err:
                raise HTTPException(400, f"start is a local ISO time such as 2026-10-17T07:50, not {start!r}") from err
        desk.reset()
        texts.reset()
        sites.reset()
        await hands.reset()
        return {"now": clock.now().isoformat()}

    @t.post("/frame")
    async def test_frame(request: Request) -> dict[str, Any]:
        desk.take_frame(_image(await request.body()), clock.now().isoformat())
        return {"accepted": True, "at": desk.frame_at}

    @t.post("/advance")
    async def advance(request: Request) -> dict[str, str]:
        seconds = (await _json(request)).get("seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
            raise HTTPException(400, "seconds is a number")
        try:
            clock.advance(seconds)
        except ValueError as err:
            raise HTTPException(400, str(err)) from err
        return {"now": clock.now().isoformat()}

    @t.get("/texts")
    def get_texts() -> list[dict[str, Any]]:
        return list(texts.sent)

    @t.get("/browser")
    async def browser() -> dict[str, Any]:
        return await hands.view()

    @t.post("/sites")
    async def set_site(request: Request) -> dict[str, Any]:
        data = await _json(request)
        try:
            site = sites[str(data.get("site"))]
            if "fault" in data:
                site.set_fault(data["fault"])
            if "prices" in data:
                if not hasattr(site, "set_prices"):
                    raise SiteError(f"{site.name} sells nothing; only the stores take prices")
                if not isinstance(data["prices"], dict):
                    raise SiteError("prices is an object of product slug to price")
                site.set_prices(data["prices"])
        except SiteError as err:
            raise HTTPException(400, str(err)) from err
        return site.describe()

    @t.get("/sites/{name}/ledger")
    def ledger(name: str) -> list[dict[str, Any]]:
        try:
            return sites[name].ledger
        except SiteError as err:
            raise HTTPException(404, str(err)) from err

    return t
