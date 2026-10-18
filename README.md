# Handled

Hold a parking ticket, a bill or a product up to the laptop's webcam; Handled names
it, does the chore in a browser you can watch, and pauses before anything is paid,
filed or ordered. The contract is `features/` (the feature files, the fence, the
needs ledger, DESIGN.md, the docket); the build plan is `docs/BUILD-PLAN.md`.

Stub (P0). The full README (install, keys, the demo script) is written in PS.

    npm ci && npm run setup:py   # Node deps; Python 3.11 venv with Playwright's Chromium
    npm run test:fast            # an agent's lane: lint, typecheck, pytest, the named FEATURES
    npm test                     # the gate's lane: everything
    npm run validate             # strict feature lint + strict docket lint
    python -m app --test         # the app in test mode (virtual clock, fixture sites, /test/*)

Keys live in `.env` (git-ignored). Tests never read it and never leave loopback: the eye
replays the Gemini answers recorded under `test/cassettes/`, and a request with no cassette
fails loudly. A changed prompt or fixture image needs its cassette recorded once, live:

    node --env-file=.env scripts/py.mjs scripts/record-cassettes.py   # prints model id, cassette names and sizes only

Live mode (what the demo integration runs; exercised by hand, never by a test):

    npm run app                        # real clock, live Gemini, headed Chromium, the real sites
    HANDLED_SITES=fixtures npm run app # the same against the fixture sites served on this port

`npm run app` loads `.env` into the environment (node's `--env-file-if-exists`); the app reads
keys from the environment only. `GEMINI_API_KEY` is required. Texts go through the first sender
whose keys are present: Photon (`PHOTON_API_KEY`, `PHOTON_PROJECT_ID`, optional
`PHOTON_AGENT_HANDLE`, the shared iMessage number; text that number once from the phone first,
since a shared line never sends first), else Twilio (`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`,
`TWILIO_FROM`, `TWILIO_TO`), else the app's log. Keep the desk's page open: its requests move
the live desk's clock (the five seconds, the day-before text).
