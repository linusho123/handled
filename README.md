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

Keys live in `.env` (git-ignored). Tests never read it and never leave loopback.
