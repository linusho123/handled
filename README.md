# Handled

Hold a parking ticket, a bill or a product up to the laptop's webcam. Handled names it in a
few seconds, does the chore in a browser you can watch, pauses before anything is paid, filed
or ordered, and texts you what it did and the deadline. LA Hacks AI Hackathon 2026.

- **Ticket:** the city's pay-or-contest page with the citation filled in. *Pay* fills the card on
  file and pauses. *Contest* writes a one-paragraph letter from the reason you say, pastes it in,
  and pauses.
- **Bill:** the biller's payment page with the account and amount filled in, paused. No page or a
  login wall: the card shows the number printed on the bill, "call to pay".
- **Product:** three store tabs and a card ranking the prices cheapest first. *Buy* reaches
  checkout with the card on file and pauses.
- **Nothing irreversible without you.** Every pay, buy or submit stops on its final page with a
  Confirm control. Tap it or say "yes". Walk away and it waits forever; a timer cannot confirm.
- **Report.** A card and one text at every end; a second text the day before a deadline.
- **Honest failure.** A page that does not answer, a citation not found, a login wall: the card
  names the step that failed and the browser stays there. A CAPTCHA pauses for you to type it.

The contract is `features/` (five feature files, 78 scenarios after expansion; the fence
`OUT-OF-SCOPE.md`; the needs ledger `USER-NEEDS.md`; `DESIGN.md`; the docket `DOCKET.md`,
D1–D39, signed at D35). The feature files bind, `DESIGN.md` bounds, the ledger explains. The
build plan is `docs/BUILD-PLAN.md`; every phase ran through a builder, two cold reviewers, a
head reviewer with mutation probes, a fix round and a gate. Every scenario is bound to the far
side: the city's, the biller's and the stores' own ledgers, the browser's DOM, the texts fake.

## Run it

    npm ci && npm run setup:py     # Node deps; a Python 3.11 venv (uv) with Playwright's Chromium
    cp .env.example .env            # then fill in the keys below
    npm run app                     # live mode: http://127.0.0.1:8080/

Live mode is the real clock, live Gemini, a headed Chromium you can watch, and the text sender
your keys select. Open the page, allow the camera, hold something up. **Keep the page open:** its
polling moves the live desk's clock (the five-second rule and the day-before text).

    HANDLED_SITES=fixtures npm run app   # the demo: the fixture city, biller and stores served on this port
    npm run app -- --port 8089           # another port

### Keys (`.env`, git-ignored; the app reads them from the environment only)

| Key | Needed for |
|---|---|
| `GEMINI_API_KEY` | Identification, the variant question, the contest letter. Required. |
| `PHOTON_API_KEY`, `PHOTON_PROJECT_ID`, `PHOTON_AGENT_HANDLE` | Texts over iMessage through Photon. Add your phone on the project's iMessage page, take the assigned shared number, and **text it once from your phone first**: a shared line never sends first. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `TWILIO_TO` | Texts over SMS when Photon is not configured. |
| `HANDLED_LIVE_MODEL` | Optional. The live vision model; default `gemini-3.5-flash-lite` (about one second a frame). Overloaded models fall through to the next lite model. |

With neither text sender configured, texts go to the app's log.

## The demo

Runs against the fixture sites (`HANDLED_SITES=fixtures`), styled after the real pages and
declared as fixtures in their footers. Why: the real Los Angeles citation pages put a CAPTCHA
before anything else, and Target and Walmart refuse automated browsers (see the fence). The
fixture stores list whatever the camera names, at a stable made-up price per store.

1. Hold the ticket up (a print or a phone screen works; fill the frame, keep the light on it).
   The card names it, a Chromium window opens on the city page with the citation filled in,
   and the card offers Pay and Contest.
2. Say or type `contest, the meter was broken, I put in two dollars`. The letter appears on the
   card and in the city's form; Confirm shows; your phone gets a text. Nobody taps Confirm.
3. Tap **Start over**. Hold up the product. Three tabs open; the card ranks the stores with
   Buy on the cheapest. Tap Buy: checkout, paused at Confirm.
4. No camera, or a product the eye cannot name? Type it in the say box while nothing is identified
   (`JBL Clip 4`) and the stores are searched for those words.
5. Tap **Next** or **Start over** for the next thing. A chore that has ended ignores the camera
   until you do, so one thing means one chore and one text.

Against the real sites (`npm run app` with no `HANDLED_SITES`), the ticket chore opens the real
Los Angeles lookup, fills the citation number, and asks you to type the CAPTCHA in the browser;
the pages after it are unconfirmed (fence, D37).

## Develop

    npm run test:fast            # an agent's lane: lint, typecheck, pytest, the FEATURES named (all when unset)
    npm test                     # the gate: everything
    npm run validate             # strict feature lint + strict docket lint
    npm run manifest             # writes and stages run-manifest.ndjson
    python -m app --test         # the app in test mode: virtual clock, fixture sites, /test/* endpoints

Tests never read `.env` and never leave loopback. The eye replays the Gemini answers recorded
under `test/cassettes/`; a request with no cassette fails loudly. A changed prompt or fixture
image needs its cassette recorded once, live:

    node --env-file=.env scripts/py.mjs scripts/record-cassettes.py   # prints model id, cassette names and sizes only

Layout: `app/eye` (the webcam frame to a named thing and its fields), `app/hands` (Playwright,
the chores, the site map with the real and fixture selectors), `app/desk` (the card, the
Confirm gate, the clock, deadlines, texts), `app/web` (the server and the page),
`test/sites` (the fixture city, biller and stores, each with a far-side ledger),
`test/steps` (TypeScript step bindings on gherkin-node-test), `test/py` (unit tests).

## What is deferred

On the fence in `features/OUT-OF-SCOPE.md`: the real Los Angeles pages after the CAPTCHA (no
real citation was in hand), live store search (two of three stores block automation), the
Browser Use finder for unknown billers and cities (its cassette could not be recorded on the
day), tickets from other cities, saved logins. Everything else in the contract is built.
