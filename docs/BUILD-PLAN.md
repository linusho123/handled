# Build plan — Handled

The reviewed contract is `handled/features/`: five feature files (identify, ticket, bill, product, report: 50 scenarios after outline expansion, 10 outlines), `OUT-OF-SCOPE.md` (the fence), `USER-NEEDS.md` (the ledger), `DESIGN.md` (bounds the build) and `DOCKET.md` (D1–D35 and N1–N3, signed at D35 on 2026-10-18). The feature files bind, `DESIGN.md` bounds, the ledger explains. Written 2026-10-17 late evening at the event; hacking ends **Sunday 2026-10-18 12:00 PM PDT, no grace period**. Two humans build; the pipeline is the crew.

Every agent that runs a phase reads this file itself. It is written so that a model with no other context can run its phase from this file plus the repository.

## Who runs what

- **Operator:** the human in the main Claude Code session. Runs `/build-pipeline <phase>` one phase at a time, answers questions, integrates, gives the go-ahead. The operator never builds inside a phase, with one exception: **the demo integration against real sites (PD) is operator-led**, because the real pages, the webcam and the test Visa are at the operator's desk, not in an agent's sandbox. **Pre-authorization:** the operator may authorize up to two further phases in writing; the main session still integrates and stops at the first block or question. **Stall rule:** on the second block verdict of any phase, the operator may finish that phase by a direct build in the main session (still binding its scenarios, still running its gate, still committing the manifest).
- **Models.** Builder, head reviewer, fixer: Opus (`claude-opus-5-5`). Cold reviewers, verifier, gate: Sonnet (`claude-sonnet-5-5`). Pass the overrides on every run:

      /build-pipeline P0 models={"builder":"claude-opus-5-5","reviewer":"claude-sonnet-5-5","head":"claude-opus-5-5","fixer":"claude-opus-5-5","gate":"claude-sonnet-5-5"}

- **Context budget (main session).** Verdicts only, never diffs. After every phase: a treecontext resume pointer (`metadata {"kind":"plan","next_session":true,"status":"active"}`, `supersedes` the previous) naming the phase merged, its commit, the next phase, open questions.
- **Reserved files** (no agent edits them; a needed change is a question to the operator): `features/*.feature`, `features/DOCKET.md`, `features/OUT-OF-SCOPE.md`, `features/USER-NEEDS.md`, every `[ruled: …]` line in `features/DESIGN.md`. The `wip` register only shrinks.
- **The repository.** `handled/` is its own git repository (P0 runs `git init`; default branch `main`). It sits inside `/Users/linus/Documents/LAHacks_AI_2026`, which is a different, live checkout: never run git there, never switch its branches.

## Process, every phase

1. **Cold builder** (Opus) on branch `pN-<name>` from `main`, this plan as its brief. Builds the phase and nothing beyond it, binds the phase's scenarios with far-side assertions, runs a mutation probe per newly bound scenario group (break the app so the group turns red, confirm, restore), runs the full suite, commits. Ambiguity goes to `openQuestions`, never a guess.
2. **Two cold reviewers** (Sonnet), read-only, independent: one on contract fidelity and test honesty (the `/audit` rubric at `~/gitrepos/gherkin-node-test/plugins/audit/skills/audit/rubric.md`); one on the phase's named risk.
3. **Head reviewer as integrator** (Opus): confirms or rejects findings against the code, runs its own probes, produces `mustFix`, `questions`, verdict (ship / fix / block).
4. **One fix round** (Opus): a failing test before each fix; a surviving probe is fixed by strengthening the binding, never by rewording a scenario. A **fresh verifier** checks each fix's test fails before and passes after.
5. **Gate** (Sonnet runs the commands): the phase's gate commands, in order. Red blocks.

**Two lanes.** Everyone inside a phase runs `npm run test:fast` (oxlint, typecheck, Python unit tests, and only the feature files the phase binds: `FEATURES=<files> npm run test:fast`). Only the gate runs `npm test` (everything). P0 defines both.

6. **Integrate** (main session): merge to `main`, commit the run manifest, store the pointer, report, **stop for the go-ahead**.

## Acceptance bars, every phase

- **Far-side assertions.** "The user sees on the card …" binds to a fetch of the desk's state through the page's own endpoint (`GET /desk` returns what the page renders: the card's fields, the controls showing, the question asked), never a flag the chore set about itself. "The user sees the browser on …" binds to Playwright's view of the real browser the app drives: its page URL and the filled field values read from the DOM (`GET /test/browser` returns url, title, filled fields and open tabs as the app's Playwright sees them), never the app's own log of what it typed. "The city's records show …", "the biller's records show …", "Walmart's records show …" bind to the **fixture site's ledger** (`GET /test/sites/<site>/ledger`), which only the fixture site writes when a form actually posts to it; never to anything the app wrote. "The user's phone receives a text" binds to the texts fake's capture (`GET /test/texts`).
- **Mutation-checking.** Every bound scenario group turns red under a deliberately broken app; probes are listed in the builder's report and the head reviewer re-runs a sample. Obligatory probes: a Confirm that is tapped by a timer (must stay red for D6); a pay or submit step that posts without the Confirm gate (D7); a card that shows "Hold it closer" at four seconds (D5); a deadline computed from today instead of the printed issue date (D13); a ranking that is not by price (D16); a second text sent for a product (D21).
- **The fence holds.** No textbook chore (D22), no login ever attempted (D26), no autonomous payment (D2, D7), no mobile app (D24). A test card at the demo (D25).
- **Numbers come from the rulings.** Five seconds to identify (D4, D5); twenty-one days from the issue date (D13); three stores (D16); nine in the morning the day before (D20). A build that needs another number asks.
- **Register.** A feature file leaves `wip` only when every scenario in it is bound; outline rows a later phase binds are held by scenario-scoped `wip`. The run manifest (`{"run-manifest":1}`) is committed every phase.
- **No live calls in tests.** Gemini (identification, the contest letter, the variant question) and Browser Use go through one client with record-and-replay cassettes under `test/cassettes/`; a missing cassette fails loudly. Texts go through an interface with a fake; the fast lane never touches the network past loopback (`test/setup/no-network.ts`, copied from Taken).
- **Tests are cheap.** The eye is driven by **fixture images** (`test/fixtures/images/`: a rendered LA parking ticket, an LADWP bill, a Cholula bottle, a blurred ticket, a blank sheet, a mug, generated by `test/fixtures/make-images.py` with Pillow so the fields are known) pushed with `POST /test/frame`; the hands are driven against **fixture sites** the test server hosts; time is a **virtual clock** (`POST /test/advance {"seconds": n}`); no scenario waits real time. The app under test starts once per test worker; Playwright's Chromium is headless in tests.

## Architecture the phases assume (from DESIGN.md; the build's choices are marked)

- `app/eye/` — Python 3.11. `Frame` in (JPEG bytes from the page's `getUserMedia` capture or a fixture PNG), `Identification` out: `kind` (ticket | bill | product | unknown), `fields` (per kind), `variant_question` (optional), `confidence`. `GeminiEye` (`google-genai`, model id confirmed by P0 against the models list; the Taken plan used `gemini-3.8-flash`) behind `Cassette` (request hash → stored response; `HANDLED_RECORD=1` records). The five-second clock belongs to the desk, not the eye: the desk starts the clock at the frame, and at five seconds of virtual time with no identification shows "Hold it closer" (D5). [chosen]
- `app/hands/` — Playwright (Python, Chromium). `Chore` base with `steps`, each step either `fill`, `navigate`, `read`, or `gate` (the Confirm gate: the step blocks on `Desk.confirmed` and nothing posts before it). `TicketChore` (lookup → fill citation + plate → Pay or Contest → payment or contest form → gate → submit), `BillChore` (find payment page → fill account + amount → gate → pay; no page → `call to pay` with the printed number), `ProductChore` (variant question → three store tabs → read prices → ranked card → Buy → cart → checkout → gate → place order). `SiteMap` names the URL and the selectors per site: fixture sites in tests, real sites at the demo (`HANDLED_SITES=fixtures|real`). `BrowserUseFinder` (the sponsor library, Gemini as its model, cassette-replayed) finds a page the `SiteMap` does not know. A failed step raises `StepFailed(step, page_url)`; the desk shows the step's name and the browser stays. [chosen]
- `app/desk/` — the card state (`identified`, `done`, `deadline`, `link`, `controls`, `question`, `failed_step`), the Confirm gate (`confirm()` from a tap or a spoken yes; no other path), the `Clock` (real or virtual), `Deadlines` (printed due date, else issue date + 21 days for tickets; bills carry theirs; products none), `Texts` (interface; `FakeTexts` in tests; Photon then Twilio at the demo), the day-before scheduler (at 09:00 local the day before, on the clock), the report (`report()` at every chore end: card + one text). [chosen]
- `app/web/` — the HTTP server (FastAPI + uvicorn) serving the page (`/`), `GET /desk`, `POST /frame`, `POST /confirm`, `POST /say {"text"}`, and under `--test`: `POST /test/reset`, `POST /test/frame`, `POST /test/advance`, `GET /test/texts`, `GET /test/browser`, `POST /test/sites {"site","fault"}`, `GET /test/sites/<site>/ledger`. The page: webcam view, card, Confirm button, microphone button (browser speech recognition where available, else a text box). [chosen]
- `test/sites/` — fixture sites served by the test server under `/sites/<site>/…`: `la-citations` (lookup form; result page; pay form with a card; contest form with a letter; `login` fault variant; `down` fault returns nothing; `notfound` fault), `ladwp` (payment page with account + amount; `login`, `down`, `nopage` faults), `target`, `walmart`, `amazon` (search → product page with a price set per scenario; cart; checkout with address + card + place order; `nolisting` fault). Each site appends to its ledger only on a real form post to its submit/pay/order route. [chosen]
- `test/` — gherkin-node-test runs `features/` with TypeScript step bindings in `test/steps/` that spawn the Python app in `--test` mode once per worker and drive it over HTTP (`test/harness/app.ts`, copied from Taken and renamed); cassettes under `test/cassettes/`; Python unit tests in `test/py/`.
- Deployment: the laptop runs the app (`npm run app`), Chromium headed, the page open in a second window; the operator's phone receives the texts.

## Pre-decided so P0 never asks

Python 3.11 in a uv venv (`npm run setup:py`), `playwright` with Chromium installed by `npm run setup:py`, `google-genai`, FastAPI + uvicorn, Pillow for fixtures, pytest; TypeScript step bindings on gherkin-node-test 0.11.0 with Vitest 4, oxlint, `@bingh/docketry` 0.1.0; `scripts/py.mjs`, `scripts/lane.mjs`, `scripts/lint-features.mjs`, `test/setup/no-network.ts`, `test/harness/app.ts` copied from `../taken` with `TAKEN_` renamed `HANDLED_`; the desk's state as one JSON document; the virtual clock over HTTP; cassettes for Gemini and Browser Use; a fake for texts; the test Visa number `4242 4242 4242 4242` as the card on file in test mode and at the demo. Gemini key from Google AI Studio in `.env` (`GEMINI_API_KEY`), never committed.

## Schedule

Phase order follows the cut order inverted (never-cut first), with the demo integration against real sites early, because real pages are the schedule risk. Hours are agent wall-clock with Opus building.

| Phase | Builds | Binds | Hours | Demo-able after? |
|---|---|---|---|---|
| P0 | scaffold, lanes, fixture images, fixture sites, the app skeleton with test mode | nothing (smoke only) | 1.25 | no |
| P1 | identify + the ticket chore: the eye with cassettes, the desk and the Confirm gate, `TicketChore` against `la-citations` | `identify.feature`, `ticket.feature` | 2 | yes, on fixtures |
| P2 | the report: the card at every chore end, one text, the day-before text, deadlines | `report.feature` | 1 | yes |
| PD | **demo integration (operator-led):** the real LADOT citation page in the `SiteMap`, the webcam on a real ticket, Gemini live, Photon or Twilio live, the demo rehearsed | none (integration gate) | 1.5 | **the demo** |
| P3 | the product chore: variant question, three store tabs, ranked card, Buy to checkout | `product.feature` | 1.5 | yes |
| P4 | the bill chore | `bill.feature` | 1 | yes |
| PS | ship: README, video, Devpost, the fence's deferred list for anything unbuilt | — | 1.25 | — |

Cumulative ≈ 9.5 hours against ~12 remaining at the time of writing. If PD slips past two hours, PS starts anyway; P4 then the Buy step of P3 then the day-before text of P2 are the first to go, in that order, per D29.

## P0 — Scaffold, lanes, fixtures, skeleton

**Builds.** `handled/` as a git repository: `package.json` (gherkin-node-test, vitest, oxlint, typescript, @bingh/docketry; scripts `test`, `test:fast`, `lint:features`, `validate`, `docket`, `docket:strict`, `manifest`, `app`, `fixtures`, `setup:py`); `pyproject.toml` with the `app` package and pytest; `scripts/` copied from Taken; `test/harness/app.ts` (spawns `python -m app --test --port <free>` once per worker, waits for `/test/reset`); `test/fixtures/make-images.py` (renders the fixture images with known fields); `test/sites/` with the seven fixture sites and their ledgers and faults; the app skeleton with `Clock`, the desk's state document, Playwright started against the fixture sites, every `/test/*` endpoint stubbed honestly (returning empty, never fake data); `features/` registered with every file in `wip`; `run-manifest.ndjson` committed with the smoke run; `.gitignore` (`.env`, `.venv`, `node_modules`, `test/cassettes/*.tmp`); a `README.md` stub.
**Binds.** Nothing. Gate = `npm test` green on an empty register plus `python -m app --test` answering `/test/reset` and `GET /test/sites/la-citations/ledger` returning an empty ledger.
**Second reviewer's focus.** Harness honesty: the test-mode endpoints must not pre-seed anything a later phase could pass with; each fixture site's ledger must be written only by that site's own submit/pay/order route (a unit test posts to the route and reads the ledger; another reads the ledger after only visiting the page and finds it empty).
**Gate.** `npm run validate` (strict feature lint + docket strict); `npm test`; `git status` clean after `npm run manifest`.

## P1 — Identify and the ticket chore

**Builds.** `GeminiEye` behind `Cassette` with cassettes recorded once for the six fixture images (the operator records with a real key before P1 or the builder asks); the desk's five-second clock and "Hold it closer"; the variant question for the product image with the size hidden (identification only; the store search is P3, so the D8 scenarios' store steps are bound in P3 and held by scenario-scoped `wip` here); `TicketChore` against `la-citations` with every step, Pay and Contest, the contest letter from the spoken reason through Gemini (cassette), the Confirm gate, the three faults, the walk-away case on the virtual clock, the issue-date deadline.
**Binds.** `identify.feature` (the D4 and D5 outlines and the clock outline; the two D8 scenarios bound through their identification steps, with their store steps held for P3), `ticket.feature` (every scenario).
**Second reviewer's focus.** Gate honesty: there must be exactly one code path that posts a pay or contest form and it must be unreachable without `Desk.confirmed`; a probe that adds a timer-driven confirm must turn the walk-away outline red; a probe that posts before the gate must turn "Pay fills the card on file and pauses before submit" red through the ledger assertion, not through the desk.
**Gate.** `FEATURES=features/identify.feature,features/ticket.feature npm run test:fast`; `npm test`; manifest.

## P2 — The report

**Builds.** `report()` at every chore end (confirmed, paused, failed): the card's `identified`, `done`, `deadline`, `link`; one text through `Texts`; `Deadlines` for tickets and bills; the day-before scheduler on the clock at 09:00 local; no second text for products. Also the **live mode** PD needs (added 2026-10-18 after P1, the operator's amendment): `npm run app` without `--test` runs the real clock, live Gemini through the same client with `HANDLED_RECORD` off and no cassette required, headed Chromium, `HANDLED_SITES=real` reading the real URLs and selectors from the `SiteMap`, the webcam page posting frames to `POST /frame`, and the real `Texts` sender chosen by the keys present (Photon with the handshake conversation, else Twilio, else a logged fake). Live mode is exercised by hand in PD, not by scenarios; the fast lane stays cassette-only.
**Binds.** `report.feature` (every scenario).
**Second reviewer's focus.** Clock honesty: every assertion on virtual time; a probe that schedules the second text at the deadline instead of the day before must flip the D20 outline; a probe that schedules one for products must turn the D21 scenario red.
**Gate.** as P1 with its file.

## PD — Demo integration (operator-led, after P2)

**Does.** `HANDLED_SITES=real`: the LADOT citation site (Los Angeles pays and contests parking citations through its ETIMS vendor pages; the operator confirms the live URLs and selectors against the page and writes them into the `SiteMap`); the webcam on a real or printed LA ticket; Gemini live (`HANDLED_RECORD=1` off); Photon if its beta works at the venue, else Twilio, else the fake with the fence updated. Photon specifics (from its beta docs, 2026-10-18): the free plan gives shared iMessage assignments, and a shared line cannot send an unsolicited first message, so the operator adds their own iPhone number on the project's iMessage page, gets the assigned shared number (`PHOTON_AGENT_HANDLE`), and texts it once from that iPhone before the demo; the app then finds that inbound message (list messages, `direction: received`, platform `imessage`), keeps its `space.id` and `receivedBy.id`, and every Handled text is a `sendMessage` into that space with a stable idempotency key per chore event. The key needs `project:read` and `project:write` only. SMS through Photon needs a campaign-registered SMS line and is not attempted; an Android phone falls back to Twilio. The demo rehearsed three times to the Confirm pause and never past it (D25). If the real citation page cannot be driven in ninety minutes, the demo runs the ticket against the fixture `la-citations` site styled to look like a city page, and the pointer records that the real-site step is deferred.
**Gate (manual, written into the pointer):** a real ticket held to the webcam is named within five seconds; the browser reaches the filled citation page; Pay reaches the payment page and pauses; the operator's phone receives the text.

## P3 — The product chore

**Builds.** `ProductChore`: the variant question's answer path (the D8 store steps), three store tabs against the fixture stores, prices read from the DOM, the ranked card with ties kept in store order, `not found` per store, no Buy with none found, Buy to cart and checkout with the address and the test Visa, the Confirm gate, the ledger on place-order.
**Binds.** `product.feature` (every scenario); the held D8 store steps in `identify.feature`.
**Second reviewer's focus.** The ranking is by the price read from the page, not by a store order or a cassette; a probe that reverses the comparison must flip every row of the D16 outline; a probe that places the order before the gate must turn "Buy goes to checkout … and pauses" red through Walmart's ledger.
**Gate.** as P1 with its files.

## P4 — The bill chore

**Builds.** `BillChore`: find the biller's payment page through the `SiteMap` (fixture `ladwp`) and, for an unknown biller, `BrowserUseFinder` (cassette). Browser Use is not installed before this phase (the operator's ruling, 2026-10-18: not until it is necessary); this phase adds `browser-use` to the Python dependencies, records its cassette once against the fixture biller, and if the install or the recording fails in thirty minutes the unknown-biller path is `call to pay` and the fence records the finder as deferred; fill account and amount; the Confirm gate; the three faults with `call to pay` and the printed number.
**Binds.** `bill.feature` (every scenario).
**Second reviewer's focus.** The phone number on the card comes from the identification's fields (the bill's own print), never from a lookup; a probe that pays before the gate must turn the first scenario red through the biller's ledger.
**Gate.** as P1 with its file.

## PS — Ship

README (install, keys, `npm run app`, the demo script), the 2–3 minute video (a ticket held up, the card naming it in under five seconds, the browser filling the city's page, Pay pausing at Confirm, the text arriving; a product ranked across three tabs), Devpost (Track 3; Gemini, Browser Use, Photon as applicable), and `OUT-OF-SCOPE.md` updated under Deferred with anything unbuilt (by the operator, since the fence is reserved). Submit before 11:30 AM.

## The demo (rehearsed Sunday 09:00–11:00, three runs)

Laptop open, webcam live, the card blank. Judge holds up the parking ticket. Within five seconds the card reads *parking ticket, citation 4512087733, plate 8ABC123, due Nov 2*. A Chromium window opens on the city's page; citation and plate type themselves in. The card offers Pay or Contest. Operator says *"contest, the meter was broken."* A paragraph appears on the card and in the city's form. The card shows Confirm. Nobody taps it. The operator's phone buzzes: *Ready to contest citation 4512087733, waiting for you. Due Nov 2.* Then the hot sauce: three tabs open, the card ranks Walmart, Target, Amazon, Buy on the cheapest. Forty-five seconds, nothing staged.
