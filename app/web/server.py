"""The HTTP server: the page, the desk's endpoints, and in test mode the /test/* endpoints
and the fixture sites (BUILD-PLAN.md, "Architecture").

Every /test/* endpoint reports what the app holds; none pre-seeds anything.
POST /confirm and POST /say ("yes") are the only callers of Desk.confirm, the
Confirm gate's one way through (D7); no timer and no clock tick reaches it.

The desk's clock moves the desk (Desk.tick: the five seconds, the day-before
texts) only when something reads it: in test mode POST /test/advance; live, every
request the desk's page makes (it polls GET /desk twice a second and posts a frame
every second), so the app itself schedules nothing.
"""

from __future__ import annotations

import asyncio
import io
import math
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from PIL import Image, UnidentifiedImageError

from app.desk import Clock, Desk, FakeTexts, VirtualClock
from app.desk.texts import Texts
from app.desk.clock import VirtualTimeLoop
from app.eye import GeminiEye
from app.eye.cassette import CassetteMissing
from app.hands import Hands
from app.hands.chores import chore_for
from app.hands.sitemap import SiteMap

PAGE = Path(__file__).with_name("page.html")


def _image(body: bytes) -> tuple[bytes, str]:
    """The frame and its media type, if it is a PNG or JPEG image; else a 400."""
    try:
        with Image.open(io.BytesIO(body)) as img:
            if img.format not in ("PNG", "JPEG"):
                raise HTTPException(400, f"a frame is a PNG or JPEG image, not {img.format}")
            kind = "image/png" if img.format == "PNG" else "image/jpeg"
            img.verify()
    except (UnidentifiedImageError, OSError, SyntaxError) as err:
        raise HTTPException(400, "a frame is a PNG or JPEG image") from err
    return body, kind


async def _frame(desk: Desk, body: bytes, at: datetime) -> dict[str, Any]:
    image, kind = _image(body)
    async with desk.lock:
        try:
            await desk.take_frame(image, kind, at)
        except CassetteMissing as err:
            # A missing cassette fails loudly, never as an invented answer.
            raise HTTPException(500, str(err)) from err
    return {"accepted": True, "at": desk.frame_at}


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
    texts: Texts | None = None,
    sites: Any = None,
    test_mode: bool = False,
    eye: Any = None,
    sitemap: SiteMap | None = None,
) -> FastAPI:
    eye = eye if eye is not None else GeminiEye()
    desk.eye = eye
    desk.clock = clock
    if texts is not None:
        desk.texts = texts
    if sitemap is not None:
        desk.chores = chore_for(hands, sitemap, eye)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await hands.start()
        try:
            yield
        finally:
            await hands.stop()

    api = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    if not test_mode:

        @api.middleware("http")
        async def tick(request: Request, call_next: Any) -> Any:
            """Live: each request reads the real clock first, so the five seconds and the
            day-before texts move with it (in test mode only POST /test/advance moves it).
            Not for the fixture sites' own pages, and never while a chore holds the desk:
            the chore's browser fetches those pages from this same server while /frame holds
            the lock, and waiting here would deadlock until the navigation timed out (seen at
            the demo integration, 2026-10-18). The next poll of /desk ticks instead."""
            if not request.url.path.startswith("/sites/") and not desk.lock.locked():
                async with desk.lock:
                    await desk.tick(clock.now())
            return await call_next(request)

    @api.get("/", response_class=HTMLResponse)
    def index() -> str:
        return PAGE.read_text(encoding="utf-8")

    @api.get("/desk")
    def get_desk() -> dict[str, Any]:
        return desk.state()

    @api.post("/frame")
    async def frame(request: Request) -> dict[str, Any]:
        return await _frame(desk, await request.body(), clock.now())

    @api.post("/confirm")
    async def confirm() -> JSONResponse:
        """A tap on Confirm: the gate's way through (D7)."""
        async with desk.lock:
            if not await desk.confirm():
                return JSONResponse({"error": "nothing is waiting for Confirm"}, status_code=409)
        return JSONResponse(desk.state())

    if not test_mode:

        @api.get("/last-frame")
        async def last_frame() -> Response:
            """Live only: the last webcam frame the desk took, so the operator can test the eye
            offline against exactly what was held up."""
            if desk.frame is None:
                raise HTTPException(404, "no frame yet")
            return Response(content=desk.frame, media_type="image/jpeg")

        @api.post("/start-over")
        async def start_over() -> JSONResponse:
            """Live only: clear the card and close every tab so the next thing can be held up,
            at any point, paused included. Nothing is confirmed or submitted by it."""
            async with desk.lock:
                desk.start_over()
                await hands.reset()
            return JSONResponse(desk.state())

    @api.post("/tap")
    async def tap(request: Request) -> JSONResponse:
        """A tap on a card control other than Confirm (Pay, Contest, Buy)."""
        control = (await _json(request)).get("control")
        if not isinstance(control, str):
            raise HTTPException(400, "control is the name of a control on the card")
        if control == "Confirm":
            return JSONResponse({"error": "Confirm is tapped through POST /confirm"}, status_code=400)
        async with desk.lock:
            if not await desk.tap(control):
                return JSONResponse({"error": f"the card does not offer {control!r}"}, status_code=409)
            if control == "Next":
                await hands.reset()  # the ended chore's tabs close with it
        return JSONResponse(desk.state())

    @api.post("/say")
    async def say(request: Request) -> JSONResponse:
        """What the user said (speech recognition on the page, or typed): a yes at the
        Confirm gate, an answer to the card's question, Pay or Contest, a reason."""
        text = (await _json(request)).get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(400, "text is what the user said")
        async with desk.lock:
            try:
                handled = await desk.say(text)
            except CassetteMissing as err:
                raise HTTPException(500, str(err)) from err
        if not handled:
            return JSONResponse({"error": "nothing on the card is waiting for that"}, status_code=409)
        return JSONResponse(desk.state())

    if test_mode:
        assert isinstance(clock, VirtualClock) and isinstance(texts, FakeTexts) and sites is not None
        api.include_router(_test_router(clock, desk, hands, texts, sites))
    if sites is not None:
        # The fixture sites: always in test mode; live only with HANDLED_SITES=fixtures (the PD fallback).
        api.include_router(sites.router())
    return api


def _test_router(clock: VirtualClock, desk: Desk, hands: Hands, texts: FakeTexts, sites: Any) -> APIRouter:
    from fixture_sites import SiteError

    t = APIRouter(prefix="/test")

    @t.post("/reset")
    async def reset(request: Request) -> dict[str, str]:
        data = await _json(request)
        start = data.get("start")
        at = None
        if start is not None:
            try:
                at = datetime.fromisoformat(str(start))
            except ValueError:
                at = None
            # The clock is naive local wall time (app/desk/clock.py): a start with an offset is refused.
            if at is None or at.tzinfo is not None:
                raise HTTPException(400, f"start is a local ISO time such as 2026-10-17T07:50, not {start!r}")
        # The hands close first: a form post the old browser context already sent can land
        # while its close is awaited, and the ledgers, texts and desk are emptied after it.
        await hands.reset()
        sites.reset()
        texts.reset()
        desk.reset()
        if at is None:
            clock.reset()
        else:
            clock.reset(at)
        return {"now": clock.now().isoformat()}

    @t.post("/frame")
    async def test_frame(request: Request) -> dict[str, Any]:
        return await _frame(desk, await request.body(), clock.now())

    @t.post("/eye")
    async def eye_delay(request: Request) -> dict[str, float]:
        """How long the eye takes to answer, in seconds of virtual time (the clock outline)."""
        seconds = (await _json(request)).get("seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 <= seconds <= 3600:
            raise HTTPException(400, "seconds is a number from 0 to 3600")
        desk.eye_delay = float(seconds)
        return {"seconds": desk.eye_delay}

    @t.post("/advance")
    async def advance(request: Request) -> dict[str, str]:
        seconds = (await _json(request)).get("seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds):
            raise HTTPException(400, "seconds is a finite number")
        try:
            clock.advance(seconds)
        except (ValueError, OverflowError) as err:
            raise HTTPException(400, str(err)) from err
        async with desk.lock:
            await desk.tick(clock.now())
        # head-1: the app's own timers run on the virtual clock too. Outside the lock,
        # so a timer's callback that takes it runs before the advance answers.
        loop = asyncio.get_running_loop()
        if isinstance(loop, VirtualTimeLoop):
            await loop.advance(seconds)
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
