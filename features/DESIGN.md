# DESIGN — Handled

The orienting document for the agent that builds Handled, with the human as secondary reader. Highest altitude only: what Handled is, the shape it must keep, and the constraints the build must not cross. Every constraint carries `ruled` (the visionary's, citing the docket entry that fixed it) or `chosen` (the agent's own call). The feature files bind; this document explains. Nobody edits it outside a discussion: the agent holds the pen, every change appends a changelog line naming the ruling that sanctioned it, a `ruled` constraint changes only by the visionary's reversal, and a `chosen` one still takes a discussion. A change with no changelog line is drift.

## Identity

- Handled turns a physical thing held up to a laptop's webcam into a finished online chore: a parking ticket becomes a filled pay-or-contest page, a bill becomes a filled payment page, a product becomes a ranked price comparison with a Buy that reaches checkout. The agent works in a browser the user can watch, pauses before anything irreversible, and reports what it did and the deadline on a card and in a text. [ruled: D1, D3, D7]
- It is a two-person hackathon build with a hard deadline of 2026-10-18 12:00 PDT and a cut order for when the time runs out. [ruled: D29]
- The textbook chore is declined; there is no mobile app. [ruled: D22, D24]

## Shape

- Three parts: the eye (the webcam frame to a named thing with its fields read), the hands (a visible browser that carries out the chore and stops at the Confirm gate), and the desk (the card the user sees, the Confirm control, the texts, the deadlines). [chosen]
- The eye answers within five seconds or says "Hold it closer" and the hands do nothing. [ruled: D4, D5]
- The Confirm gate is the hands' only way past a pay, buy or submit step; there is no time-out, no auto-confirm, no demo flag that skips it. A tap on the card or a spoken yes is the whole set of ways through. [ruled: D7, D6]
- Every field the eye reads is shown on the card before the hands type it anywhere; the user can correct a field by voice or keyboard. [ruled: D28]
- A failed step is a stopped chore: the card names the step and the browser stays on the last page it reached. Nothing is retried silently and nothing is submitted. [ruled: D10, D15, D17]
- A login wall is a failed step. Handled holds no passwords. [ruled: D26]
- The report is a card plus one text at the end of every chore and a second text the day before any deadline; a product has no deadline. The browser need not stay open. [ruled: D19, D20, D21, D3]

## Numbers the build meets

- Five seconds to identify. [ruled: D4, D5]
- Twenty-one days from the issue date when a ticket prints no due date. [ruled: D13]
- Three stores, each in its own tab, ranked cheapest first. [ruled: D16]
- The day-before text at nine in the morning local time. [ruled: D20; ratified D32]

## The chores

- Ticket: the issuing city's pay-or-contest page, LADOT for Los Angeles, other cities best effort; citation and plate filled; Pay fills the card on file and pauses; Contest writes a one-paragraph letter from the spoken reason, pastes it, shows it, and pauses. [ruled: D9, D11, D12, D27]
- Bill: the biller's payment page found, account and amount filled, paused; with no page or a login wall, the phone number printed on the bill and "call to pay". [ruled: D14, D15]
- Product: a variant question first when the size is unsettled; three stores in tabs; a ranked card; Buy adds to cart, reaches checkout with the shipping address and the Visa on file, and pauses at place-order. [ruled: D8, D16, D17, D18]

## Cut order

When the build runs short: the bill chore first, then the Buy step in favour of the ranked card alone, then the day-before text. Identification, the ticket chore, the Confirm gate and the report are never cut. Whatever is unbuilt at the deadline is recorded on the fence as deferred. [ruled: D29; ratified D34]

## The build's choices (chosen at the start of the build, 2026-10-17 late evening)

- One Python 3.11 process is the app: the eye, the hands and the desk, with an HTTP server for the web page and a test mode. TypeScript step bindings on gherkin-node-test drive it black-box over HTTP, the harness shape proven in the Taken build the same day (`scripts/py.mjs`, `scripts/lane.mjs`, `test/harness/app.ts` are copied, not rewritten). [chosen]
- The eye is Gemini vision (`gemini-3.8-flash`, the sponsor model, key from Google AI Studio) behind one client with record-and-replay cassettes under `test/cassettes/`; a missing cassette fails loudly; the fast lane never calls a model. The web page captures a frame with `getUserMedia` and posts a JPEG; in test mode a fixture image is pushed instead. [chosen]
- The hands are Playwright (Chromium, headed at the demo, headless in tests) driven by two layers: scripted flows for the pages the demo rehearses (LADOT, LADWP, Target, Walmart, Amazon), and Browser Use (the sponsor agent library, Gemini as its model, cassette-replayed in tests) for finding a page the scripts do not know: another city's citation page, an unknown biller. A scripted flow is tried first; Browser Use is the fallback, and it is not installed until the bill chore phase needs it. [chosen]
- Tests never touch a real site. The test server hosts fixture sites under `test/sites/`: a city citation portal with lookup, pay and contest forms and a login variant; a biller portal; three store fronts with search, product, cart and checkout. Each fixture site records what was submitted, paid or ordered in a ledger the step bindings read as the far side ("the city's records show nothing submitted"). Faults (no answer, not found, login wall) are set per scenario through `/test/sites`. [chosen]
- Texts go through one `Texts` interface: a fake that records in tests, Photon (the sponsor) at the demo if its beta works at the venue, else Twilio, else the fake stays and the fence records texts as deferred. Photon's shared iMessage line never sends first, so the user's phone opens the conversation once before the first chore, and every text after that is a reply into that conversation; an Android phone uses Twilio. [chosen]
- The desk is one web page (vanilla TypeScript, no framework) with the webcam view, the card, the Confirm control and a microphone button; "yes" and corrections arrive as text through the browser's speech recognition where available and the keyboard otherwise. [chosen]
- Time is a virtual clock in test mode (`POST /test/advance`); deadlines, the day-before text and the walk-away cases are asserted on fixture time, never wall time. [chosen]
- The card on file at the demo is a test Visa; the demo script stops at Confirm. [chosen; under D25]

## Changelog

- 2026-10-17 — initial draft (scope interview, compressed at the visionary's request; docket N1–N3, D1–D29). The build's `chosen` constraints added at the same sitting so P0 never asks.
- 2026-10-18 — signed at D35 after ratifications D30–D34 (N2, N3, D20, D28, D29). No `ruled` line changed.
- 2026-10-18 — Photon's first-message constraint recorded under the texts `chosen` line after reading its beta docs; the build plan's PD section carries the setup steps. No `ruled` line changed.
- 2026-10-18 — Browser Use deferred to the bill chore phase at the operator's word (not until necessary); the ticket and product chores run on scripted Playwright flows alone. No `ruled` line changed.
- 2026-10-18 — live mode (real clock, live Gemini, headed Chromium, real sites, real texts) assigned to P2 in the build plan so the demo integration phase has something to run; a build-plan scheduling change, no `ruled` or `chosen` line changed.
