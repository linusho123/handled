# User needs — Handled

The needs ledger for Handled, reconciled from the interview record on 2026-10-17 late evening (docket dates are UTC, 2026-10-18). Every need is an N entry in `DOCKET.md`. The ledger explains and prioritizes; it never specifies. At build, only the feature files bind: a `partial` status is a ratified stopping point, not debt, and a builder who believes the ledger implies missing behavior raises the question rather than building from the ledger.

Beneficiaries: **user** is the person with the pile of physical things (the visionary is the primary user); **team** is the two-person hackathon team building and demoing Handled.

## Needs

- **N1** (user, wt 5) — *I need the pile of physical things that each mean an online chore, a ticket, a bill, a product, a textbook, a form, to be handled by showing the thing to a camera, so the agent identifies it, does the chore in a browser I can watch, and tells me what it did and when the deadline is.* The vision, the interviewer's reflection accepted by proceeding to the first decision. Evidence: D1, D3, D4, D5, D8, D9, D10, D12, D13, D14, D15, D16, D17, D19, D20, D21, D22, D23, D24, D26, D27, D29 — the three chores, the identification and its failure case, each chore's path and failure case, the report and the reminder, the declined textbook and sweeps, the fence. Coverage: `scenario` — identify.feature, ticket.feature, bill.feature, product.feature, report.feature; plus `structural` for D29 in DESIGN.md. Coverage note: the textbook and the form named in the vision are on the fence (D22 declined; forms never selected), so the need is met for the three chores of D1.
- **N2** (user, wt 4) — *I need nothing irreversible to happen with my money or my name unless I tapped for it.* Laddered by the interviewer from the visionary's choice of stop-and-ask every time (D2) over autonomous pay-then-report; weight ratified at the sign read (D30). Evidence: D2, D6, D7, D11, D12, D14, D18, D25, D28 — the Confirm gate, its walk-away failure case, the four steps that pause behind it, the test-card assumption, the fields-shown assumption. Coverage: `scenario` — ticket.feature, bill.feature, product.feature (the Confirm and walk-away scenarios); plus `structural` for D29 in DESIGN.md (the gate is never cut).
- **N3** (team, wt 4) — *We need Handled demoable at every hour mark from the first chore on, because the deadline is noon and the game master entry stalled.* From the invocation; laddered by the interviewer; ratified at the sign read (D31). Means: the cut order (D29). Evidence: D29. Coverage: `structural` — the cut order in DESIGN.md. Tensions: caps N1 (the bill chore is the first cut) and N2 only in the sense that the Buy step may be unbuilt; the gate itself is never cut.

## Candidate needs with no interview evidence

The checklist sweep was declined (D23), so no candidate was asked. Common to products that act on a user's behalf online and unasked here: what the user sees when a site changes its layout mid-chore; how a chore is stopped by the user before Confirm; what is kept after a chore (the card, the link, the read fields) and for how long.

## Bidirectional check

- Every need above carries a status; none is uncovered.
- Every feature file appears in a need's coverage: identify (N1), ticket (N1, N2), bill (N1, N2), product (N1, N2), report (N1).
- Swap test: every statement survives its mechanism being swapped. N1 names "a camera" and "a browser I can watch", which are the visionary's own framing of the vision rather than hoisted design choices; the vision model, the browser driver and the texting service are the build's choices in DESIGN.md and appear in no need.
