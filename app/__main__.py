"""`python -m app`: the eye, the hands and the desk in one process.

  python -m app --test [--port N] [--host H]

--test runs on a virtual clock (the event loop's timers too) with the fake texts, a headless Chromium held
to loopback, the fixture sites under /sites/<site>/ and the /test/* endpoints
(app/web/server.py), and the eye replaying its cassettes (test/cassettes/).
The demo mode (real clock, headed browser, real sites, live Gemini and texts)
arrives with the demo integration (PD); only test mode runs so far.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    parser.add_argument("--test", action="store_true", help="test mode: virtual clock, fake texts, fixture sites, /test/* endpoints")
    parser.add_argument("--host", default="127.0.0.1", help="address to bind (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="port to bind (default 8080)")
    args = parser.parse_args(argv)

    if not args.test:
        print("python -m app: only --test is built so far (the demo mode is PD)", file=sys.stderr)
        return 2

    import uvicorn

    sys.path.insert(0, str(ROOT / "test" / "sites"))
    from fixture_sites import Sites

    from app.desk import Desk, FakeTexts, VirtualClock
    from app.eye import GeminiEye
    from app.hands import Hands
    from app.hands.sitemap import SiteMap
    from app.web.server import create_app

    # The fixture sites live on this server; the browser reaches them over loopback.
    sitemap = SiteMap(f"http://127.0.0.1:{args.port}")
    api = create_app(
        clock=VirtualClock(),
        desk=Desk(),
        hands=Hands(headless=True, step_timeout_ms=5_000),  # risk-1: no test waits out a long step timeout
        texts=FakeTexts(),
        sites=Sites(),
        test_mode=True,
        eye=GeminiEye(),
        sitemap=sitemap,
    )
    print(f"handled: listening on http://{args.host}:{args.port} (test mode)", flush=True)
    # head-1: the event loop runs on the virtual clock, so any timer falls due on POST /test/advance.
    uvicorn.run(api, host=args.host, port=args.port, log_level="warning", loop="app.desk.clock:VirtualTimeLoop")
    return 0


if __name__ == "__main__":
    sys.exit(main())
