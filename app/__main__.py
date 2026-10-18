"""`python -m app`: the eye, the hands and the desk in one process.

  python -m app --test [--port N] [--host H]      test mode
  python -m app [--port N] [--host H]             live mode (npm run app)

--test runs on a virtual clock (the event loop's timers too) with the fake texts, a headless Chromium held
to loopback, the fixture sites under /sites/<site>/ and the /test/* endpoints
(app/web/server.py), and the eye replaying its cassettes (test/cassettes/).

Live mode (what the demo integration, PD, runs; exercised by hand, never by a
test): the real clock, live Gemini through the same client (no cassette read,
required or written; HANDLED_RECORD ignored), a headed Chromium, the sites named
by HANDLED_SITES (real, the default: the real URLs and selectors in the SiteMap;
fixtures: the fixture sites served here, the PD fallback), the desk's page
posting webcam frames to POST /frame, and the texts sent by the first sender
whose keys are present in the environment (Photon, then Twilio, else the log;
app/desk/texts.py). Keys come from the environment only: `npm run app` loads
.env through node's --env-file; the app never opens a key file itself.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITES_MODES = ("real", "fixtures")


def _fixture_sites():
    sys.path.insert(0, str(ROOT / "test" / "sites"))
    from fixture_sites import Sites

    return Sites()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("--test", action="store_true", help="test mode: virtual clock, fake texts, fixture sites, /test/* endpoints")
    parser.add_argument("--host", default="127.0.0.1", help="address to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="port to bind (default 8080)")
    args = parser.parse_args(argv)

    import uvicorn

    from app.desk import Desk, FakeTexts, RealClock, VirtualClock
    from app.desk.texts import texts_from_env
    from app.eye import GeminiEye
    from app.eye.cassette import Cassette
    from app.hands import Hands
    from app.hands.sitemap import SiteMap
    from app.web.server import create_app

    sites_mode = os.environ.get("HANDLED_SITES", "fixtures" if args.test else "real")
    if sites_mode not in SITES_MODES:
        print(f"python -m app: HANDLED_SITES is {sites_mode!r}; it is one of {', '.join(SITES_MODES)}", file=sys.stderr)
        return 2

    if args.test:
        if sites_mode != "fixtures":
            print("python -m app --test: test mode runs on the fixture sites only (HANDLED_SITES=fixtures)", file=sys.stderr)
            return 2
        # The fixture sites live on this server; the browser reaches them over loopback.
        api = create_app(
            clock=VirtualClock(),
            desk=Desk(),
            hands=Hands(headless=True, step_timeout_ms=5_000),  # risk-1: no test waits out a long step timeout
            texts=FakeTexts(),
            sites=_fixture_sites(),
            test_mode=True,
            eye=GeminiEye(),
            sitemap=SiteMap(f"http://127.0.0.1:{args.port}"),
        )
        print(f"handled: listening on http://{args.host}:{args.port} (test mode)", flush=True)
        # head-1: the event loop runs on the virtual clock, so any timer falls due on POST /test/advance.
        uvicorn.run(api, host=args.host, port=args.port, log_level="warning", loop="app.desk.clock:VirtualTimeLoop")
        return 0

    if not os.environ.get("GEMINI_API_KEY"):
        print("python -m app: live mode needs GEMINI_API_KEY in the environment (npm run app loads .env)", file=sys.stderr)
        return 2
    fixtures = sites_mode == "fixtures"
    sites = _fixture_sites() if fixtures else None
    if sites is not None:
        # The demo on the fixture stores (D38): the catalog's prices, which a test sets per scenario
        # and live mode must seed itself. Walmart cheapest, so Buy lands there as the demo script says.
        for store, prices in (
            ("target", {"cholula-original-32oz": "9.49", "cholula-original-12oz": "4.29"}),
            ("walmart", {"cholula-original-32oz": "8.98", "cholula-original-12oz": "3.98"}),
            ("amazon", {"cholula-original-32oz": "10.99", "cholula-original-12oz": "4.99"}),
        ):
            sites[store].set_prices(prices)
    texts = texts_from_env(os.environ)
    texts.prepare()  # names the senders configured; Photon looks for the user's first message
    api = create_app(
        clock=RealClock(),
        desk=Desk(live=True),
        hands=Hands(headless=False, loopback_only=fixtures),
        texts=texts,
        sites=sites,
        test_mode=False,
        eye=GeminiEye(Cassette(live=True)),
        sitemap=SiteMap(f"http://127.0.0.1:{args.port}") if fixtures else SiteMap.real(),
    )
    print(f"handled: open http://{args.host}:{args.port}/ (live mode, {sites_mode} sites)", flush=True)
    uvicorn.run(api, host=args.host, port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    sys.exit(main())
