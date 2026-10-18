# Handled — Devpost draft (LA Hacks AI Hackathon 2026)

**One line.** Hold the thing up to your laptop's camera and the chore it stands for gets done in a browser you can watch, with a pause before anything irreversible.

## Inspiration

Everyone has the pile: the parking ticket on the fridge, the bill with a due date, the product you meant to price-check. Each one is a small online chore with a deadline you will forget. The thing itself is the interface. Handled turns it into the chore.

## What it does

- **Identify.** Hold a parking ticket, a bill or a product up to the webcam. Within five seconds the card names it and reads its fields (citation and plate; biller, amount and due date; product and size). Blurry or unknown gets "Hold it closer" and nothing else happens.
- **Do the chore in a browser you can watch.** A ticket becomes the city's pay-or-contest page with the citation filled in; *Pay* fills the card on file, *Contest* writes a one-paragraph letter from what you said out loud and pastes it in. A bill becomes its payment page, filled. A product becomes three store tabs and a card ranking the prices, cheapest first, with *Buy* that reaches checkout.
- **Nothing irreversible without a tap.** Every pay, buy or submit stops on the final page with a Confirm control. Tap it or say "yes". Walk away and it waits forever. A timer cannot confirm; the tests prove it.
- **Report.** At every end you get a card and one text: what was identified, what was done, the deadline, a link. The day before the deadline, a second text. A product has no deadline and gets none.
- **Honest failure.** A page that does not answer, a citation that is not found, a login wall: the card names the step that failed and the browser stays open there. A CAPTCHA pauses the chore for you to type it; the agent never solves one.

## How we built it

- **Contract first.** A scoping interview produced five Gherkin feature files (50 scenarios), a fence of what is out of scope, a needs ledger and a docket of 38 dated rulings with provenance, signed before any code. The feature files bind the build; a strict lint over the contract gates every phase.
- **A pipeline of agents built it, phase by phase**, each with a cold builder, two cold reviewers, a head reviewer running mutation probes, one fix round with a failing test first, and a gate. Five build phases plus a demo-integration pass, every merge green; the whole build ran between midnight and eight in the morning.
- **Eye:** Gemini vision (`gemini-3.5-flash-lite` live, about one second a frame) behind record-and-replay cassettes so the test suite never calls a model.
- **Hands:** Playwright driving a headed Chromium. In tests it drives fixture replicas of the city portal, a biller and three stores, each with a far-side ledger that only a real form post can write to, so "nothing was paid" is asserted against the site, never against the app's own word.
- **Desk:** the card, the Confirm gate (the only path to any final submit), a clock the tests control, deadlines, texts.
- **Texts:** Photon's iMessage API, replying into the conversation you open by texting the agent once.
- **Python 3.11 + FastAPI, TypeScript step bindings on gherkin-node-test, Vitest, pytest.**

## Challenges

- The real Los Angeles citation pages take a citation number and a CAPTCHA before anything else, and no plate. We read the live forms and wired them; the CAPTCHA became a ruling: the user types it, the agent waits.
- Target and Walmart refuse automated browsers. So prices are real: a Google Shopping search returns listings from many sellers, the chore keeps the lowest per store and ranks three, and Buy opens the cheapest listing for you. The cart, the checkout with the card on file and the Confirm pause for products run against fixture stores styled after the real ones, declared as fixtures.
- The default Gemini model took over two minutes on a ticket; the lite model takes a second. The five-second rule in the contract made that a hard requirement, not a preference.
- Photon's edge rejects Python's default User-Agent with a 403. One header.

## Accomplishments

- A signed behavioral contract (38 rulings, then one more after the build) and a build whose every one of the 78 scenarios is bound far-side and mutation-checked: a timer-driven confirm turns the walk-away scenarios red; a ranking by whole dollars turns the price scenarios red; a letter that merely echoes the user turns the contest scenario red.
- The Confirm gate is provably the only path to a pay, buy or submit.

## What we learned

Writing the contract first made the agents' questions precise and made "done" checkable. The scary parts of acting on someone's behalf online (money, submissions, CAPTCHAs, logins) all became rulings with tests rather than vibes.

## What's next

Saved logins for known billers, the real pages after the Los Angeles CAPTCHA (once a real citation is in hand), store APIs for live prices, more cities.

## Built with

Python, FastAPI, Playwright, Gemini, Photon, SerpApi (Google Shopping), TypeScript, gherkin-node-test, Vitest, pytest, docketry, Pillow.

## Links

- Repository: (fill in)
- Video: (fill in, 2–3 minutes: ticket held up, named in under five seconds, the city page filled, Pay pausing at Confirm, the text arriving; the hot sauce ranked across three tabs)

## Tracks and challenges

- Main track: Track 3 (fill in the exact name from the tracks page).
- Photon: iMessage/WhatsApp/SMS APIs for AI Agents (the agent texts you what it did; you text it once to open the line).
- Gemini (Google): identification, the variant question and the contest letter.
