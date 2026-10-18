docket: 1

# Handled scoping interview. Visionary: linus (two builders). Interviewer: Claude (scope 5.1.1, gnt 0.11.0, docketry 0.1.0). Started 2026-10-18 ~05:40; hard deadline 12:00 the same day. Compressed at the visionary's request: three decisions, one readback.

N1 2026-10-18 [I>V] user 5
  need: I need the pile of physical things that each mean an online chore, a ticket, a bill, a product, a textbook, a form, to be handled by showing the thing to a camera, so the agent identifies it, does the chore in a browser I can watch, and tells me what it did and when the deadline is [I>V]
# the interviewer's reflection of the vision the visionary accepted by proceeding to the first decision; weight 5.

D1 2026-10-18 [I+V]
  resp: three chores are in scope for the demo, each its own behavior area: a parking ticket (read the citation, open the city's pay-or-contest page, draft a contest letter, text the deadline), a bill or letter with a due date (read it, find the payment page, schedule or pay, text the deadline), and a product (identify it, compare prices at three stores, offer to buy at the cheapest); the textbook chore is not in scope [I+V]
  -> boundary
  serves: N1
  touches: none
# the visionary selected parking ticket, bill, and product price-compare + buy from four options; textbook declined.

D2 2026-10-18 [I>V]
  pre:   the agent is carrying out a chore in the browser [I>V]
  trig:  the next step would let money leave or submit a form: paying a bill, buying the product, filing a contest [I+V]
  resp:  the browser pauses on that final page and the user sees a Confirm control; nothing irreversible happens until the user taps Confirm or says yes; after confirmation the agent completes the step [I+V]
  sib:   none -- failure case probed at readback
  serves: N1
  touches: D1
# roads not taken: fully autonomous (pay then report); demo mode wired to a sandbox card. The visionary chose stop-and-ask every time.

D3 2026-10-18 [I+V]
  resp: the result reaches the user as a card on screen (what was identified, what was done, the deadline, a link to the page opened) and as one text message with the summary and the deadline, plus a second text the day before the deadline; the browser is not required to stay open on the final page [I+V]
  -> boundary
  serves: N1
  touches: D1 D2
# roads not taken: leaving the visible browser on the final page as the hand-off surface (not selected).

# Readback (one pass, accepted with "yes"). Entry dates are written in UTC like N1-D3 above (the readback closed 2026-10-17 ~23:40 PDT). Every entry below the readback line is interviewer-drafted and accepted as written, hence I>V; the numbers are the interviewer's, with why slots. Entries tagged [I] were never put to the visionary and await ratification at the sign read.

D4 2026-10-18 [I>V]
  pre:   the Handled web app is open on the laptop with the webcam live and nothing in front of it [I>V]
  trig:  the user holds a parking ticket, a bill with a due date, or a product up to the webcam [I>V]
  resp:  within {5 seconds} the user sees a card naming what it is and the fields read from it (for a ticket the citation number, the plate and the issuing city; for a bill the biller, the amount and the due date; for a product its name, brand and size) and a visible browser window opens and the chore for that kind begins [I>V]
  why:   {5 seconds} is the interviewer's number, read back and accepted; long enough for one vision call, short enough that the user keeps holding the thing up [I>V]
  sib:   D5
  spread: The five-second clock decides between the card and Hold it closer
  serves: N1
  touches: D1

D5 2026-10-18 [I>V] !
  pre:   the web app is open with the webcam live [I>V]
  trig:  the thing held up cannot be identified within {5 seconds}: too far away, blurred, or not one of the three kinds [I>V]
  resp:  nothing of the chore kind: the user sees `Hold it closer` on the card, no browser window opens and no page is touched [I>V]
  why:   {5 seconds} is the same number as D4; the same clock decides both [I>V]
  spread: The five-second clock decides between the card and Hold it closer
  serves: N1
  touches: D4

D6 2026-10-18 [I>V] !
  pre:   the browser is paused on a final page with the Confirm control showing, as D2 rules [I>V]
  trig:  the user walks away and never taps Confirm or says yes [I>V]
  resp:  nothing, ever: no payment, purchase or submission happens, the page stays paused with Confirm showing, and no time-out confirms on the user's behalf [I>V]
  serves: N1 N2
  touches: D2

D7 2026-10-18 [I>V] amends D2
  pre:   the agent is carrying out a chore in the browser [I>V]
  trig:  the next step would let money leave or submit a form: paying a bill, buying the product, filing a contest [I+V]
  resp:  the browser pauses on that final page and the user sees a Confirm control; nothing irreversible happens until the user taps Confirm or says yes; after confirmation the agent completes the step and the card says so [I+V]
  sib:   D6
  serves: N1 N2
  touches: D1 D2 D6
# restates D2 in full with its failure case named (D6) now that the readback probed it; the visionary's correction in D2 (stop-and-ask every time) is kept in the I+V slots; the header is the lowest slot's tag.

D8 2026-10-18 [I>V]
  pre:   the webcam shows a product the agent has identified by name and brand [I>V]
  trig:  the product comes in more than one variant and the frame does not settle which: size, count or colour [I>V]
  resp:  the user sees one question on the card, for example `Is this the 32 oz?`, and the price comparison waits for a yes or a correction before any store is searched [I>V]
  sib:   none -- a question has no failure case
  serves: N1
  touches: D4

D9 2026-10-18 [I>V]
  pre:   a parking ticket has been identified with its citation number, plate, issuing city and printed due date [I>V]
  trig:  the ticket chore begins [I>V]
  resp:  the agent opens the issuing city's pay-or-contest page (LADOT for Los Angeles) in the visible browser, fills the citation number and the plate, and the user sees the card offer Pay or Contest with the printed due date as the deadline [I>V]
  sib:   D10
  serves: N1
  touches: D1 D4

D10 2026-10-18 [I>V] !
  pre:   a parking ticket has been identified [I>V]
  trig:  the city's page cannot be reached, the citation is not found, or the page demands a login [I>V]
  resp:  nothing is submitted: the user sees on the card which step failed and the browser stays open on the last page it reached [I>V]
  serves: N1
  touches: D9

D11 2026-10-18 [I>V]
  pre:   the ticket's pay-or-contest page is filled, as D9 rules [I>V]
  trig:  the user chooses Pay [I>V]
  resp:  the agent proceeds to the city's payment page, fills the card on file, and pauses before the final submit with Confirm showing, as D7 rules [I>V]
  sib:   none -- the pause is D7's own case
  serves: N1 N2
  touches: D7 D9

D12 2026-10-18 [I>V]
  pre:   the ticket's pay-or-contest page is filled, as D9 rules [I>V]
  trig:  the user chooses Contest and says the reason out loud, for example `the meter was broken` [I>V]
  resp:  the agent writes a one-paragraph contest letter from the spoken reason, the user sees the letter on the card, the agent pastes it into the city's contest form and pauses before submit with Confirm showing, as D7 rules [I>V]
  sib:   none -- the pause is D7's own case
  serves: N1 N2
  touches: D7 D9

D13 2026-10-18 [I>V]
  pre:   a parking ticket has been identified and its issue date read [I>V]
  trig:  no due date is printed on the ticket [I>V]
  resp:  the deadline is {21 days} after the printed issue date; the card and the text say the deadline and that it was counted from the issue date [I>V]
  why:   {21 days} is the window Los Angeles gives to request an initial review of a citation; the interviewer's number, read back and accepted [I>V]
  sib:   none -- a default has no failure case
  spread: A ticket with no printed due date is due twenty-one days after issue
  serves: N1
  touches: D3 D9

D14 2026-10-18 [I>V]
  pre:   a bill or letter has been identified with its biller, amount due, due date and account number [I>V]
  trig:  the bill chore begins [I>V]
  resp:  the agent finds the biller's payment page in the visible browser, fills the account number and the amount, and pauses before paying with Confirm showing, as D7 rules; the user sees the biller, the amount and the due date on the card [I>V]
  sib:   D15
  serves: N1 N2
  touches: D1 D4 D7

D15 2026-10-18 [I>V] !
  pre:   a bill has been identified [I>V]
  trig:  no payment page can be found or reached, or the page demands a login [I>V]
  resp:  nothing is paid: the user sees on the card the phone number printed on the bill with the words `call to pay`, and the browser stays open on the last page it reached [I>V]
  serves: N1
  touches: D14

D16 2026-10-18 [I>V]
  pre:   a product has been identified by name, brand and size, with any D8 question answered [I>V]
  trig:  the product chore begins [I>V]
  resp:  the agent opens {3 stores} each in its own tab, finds the product at each, and the user sees a card ranking the three prices cheapest first with a Buy control on the cheapest [I>V]
  why:   {3 stores} is the interviewer's number, read back and accepted; enough for a ranking, few enough to fit on one card [I>V]
  sib:   D17
  spread: Prices from three stores are ranked cheapest first
  serves: N1
  touches: D1 D4 D8

D17 2026-10-18 [I>V] !
  pre:   the product chore is running [I>V]
  trig:  a store does not list the product, or its page cannot be reached [I>V]
  resp:  nothing is bought there: that store is listed on the card as `not found`, the ranking holds the stores that answered, and with no store answering the card says so and offers no Buy control [I>V]
  serves: N1
  touches: D16

D18 2026-10-18 [I>V]
  pre:   the ranked card of D16 is showing [I>V]
  trig:  the user taps Buy on the cheapest store [I>V]
  resp:  the agent adds the product to that store's cart, proceeds to checkout, fills the shipping address and the Visa card on file, and pauses at the final place-order step with Confirm showing, as D7 rules [I>V]
  sib:   none -- the pause is D7's own case
  serves: N1 N2
  touches: D7 D16

D19 2026-10-18 [I>V]
  pre:   a chore has reached its end: completed after Confirm, paused at Confirm, or stopped at a failed step [I>V]
  trig:  that moment [I>V]
  resp:  the user sees a card with what was identified, what was done, the deadline where there is one, and a link to the page the browser is on; the user's phone receives one text with the same summary and the deadline [I>V]
  sib:   none -- a report has no failure case
  serves: N1
  touches: D3 D7

D20 2026-10-18 [I]
  pre:   a ticket or bill chore has been reported with a deadline, as D19 rules [I>V]
  trig:  the day before the deadline arrives at {9 in the morning} [I]
  resp:  the user's phone receives a second text naming the chore and saying the deadline is tomorrow [I>V]
  why:   the day before is the visionary's (D3); {9 in the morning} is the interviewer's hour, not yet put to the visionary [I]
  sib:   D21
  spread: The day before a deadline brings a second text
  serves: N1
  touches: D3 D19

D21 2026-10-18 [I>V] !
  pre:   a product chore has been reported, as D19 rules [I>V]
  trig:  days pass [I>V]
  resp:  nothing of the reminder kind: a product has no deadline and no second text is sent [I>V]
  serves: N1
  touches: D20

# Needs laddered by the interviewer from the rulings, never put to the visionary; weights guessed; await ratification.

N2 2026-10-18 [I] user 4
  need: I need nothing irreversible to happen with my money or my name unless I tapped for it [I]
# the why under D2 and D7: the visionary chose stop-and-ask every time over autonomous pay-then-report. Weight 4: below the vision, above convenience.

N3 2026-10-18 [I] team 4
  need: We need Handled demoable at every hour mark from the first chore on, because the deadline is noon and the game master entry stalled [I]
# from the invocation ("software-only backup chosen after the game master stalled on networking"); the cut order D29 is its means.

# Fence: declined, deferred, assumptions. The textbook decline and the sweeps decline are the visionary's; the assumptions are the interviewer's reading of the readback's fence line, tagged I where the visionary did not say them.

D22 2026-10-18 [V]
  resp: the textbook chore (identify a textbook, find it cheaper or as a rental) is not in scope [V]
  -> fence-declined textbook-chore
  serves: N1
  touches: D1

D23 2026-10-18 [V]
  resp: the checklist sweep and the adversarial pass were declined to keep the interview short; every checklist category is declined in bulk without being probed [V]
  -> fence-declined checklist-sweep
  serves: N1
  touches: none

D24 2026-10-18 [V]
  resp: there is no mobile app; the laptop web app with its webcam is the only surface, and the phone receives texts only [V]
  -> fence-declined mobile-app
  serves: N1
  touches: D3

D25 2026-10-18 [I>V]
  pre:   the demo runs against real city, biller and store pages [I>V]
  trig:  a judge taps Confirm on a payment or a purchase [I>V]
  resp:  the card on file is a test card, so the real site declines it or a sandbox accepts it and no real money moves; the demo script stops at Confirm and does not tap it; reopens if a judge wants to see a real payment go through [I>V]
  -> fence-assumption test-card-at-the-demo
  serves: N2
  touches: D7 D11 D18

D26 2026-10-18 [I>V]
  pre:   the user has no saved logins and Handled holds no passwords [I>V]
  trig:  a chore reaches a page that demands a login [I>V]
  resp:  the agent stops there as D10 and D15 rule; reopens if the visionary wants saved logins for a known biller or store [I>V]
  -> fence-assumption no-logins
  serves: N1
  touches: D10 D15

D27 2026-10-18 [I>V]
  resp: tickets from cities other than Los Angeles are best effort: the agent searches for that city's pay-or-contest page and proceeds if it finds one, else stops as D10 rules; the demo uses a Los Angeles ticket; reopens if a judge brings a ticket from another city [I>V]
  -> fence-deferred other-cities
  serves: N1
  touches: D9 D10

D28 2026-10-18 [I]
  pre:   the webcam frame shows the thing clearly enough to read [I]
  trig:  a field is misread: a wrong digit in the citation number, a wrong amount on the bill [I]
  resp:  the card shows every field it read before the browser acts on them, and the user corrects a field by saying or typing it; the only guard against a wrong field reaching a form is that pause and the Confirm of D7; reopens if a judge's ticket is misread at the demo [I]
  -> fence-assumption fields-shown-before-use
  serves: N1 N2
  touches: D4 D7

# Structural: the cut order, the interviewer's proposal, not yet put to the visionary.

D29 2026-10-18 [I]
  resp: when the build runs short the cut order is: the bill chore of D14 first, then the Buy step of D18 in favour of the ranked card alone, then the day-before text of D20; identification (D4), the ticket chore (D9 to D13), the Confirm gate (D7) and the report (D19) are never cut; whatever is unbuilt at the deadline is recorded on the fence as deferred [I]
  -> structural
  serves: N1 N2 N3
  touches: D14 D18 D20

# Handoff read, 2026-10-18 (UTC; 2026-10-18 ~00:10 PDT). The visionary read the contract and answered "yes". Ratifications first, each under [V]; then the signature naming the last entry in effect.

D30 2026-10-18 [V] ratifies N2
  resp: the need as the interviewer laddered it, nothing irreversible with my money or my name unless I tapped for it, is the visionary's [V]
  -> boundary
  serves: N2
  touches: none

D31 2026-10-18 [V] ratifies N3
  resp: the team's need, Handled demoable at every hour mark because the deadline is noon, is the visionary's [V]
  -> boundary
  serves: N3
  touches: none

D32 2026-10-18 [V] ratifies D20
  resp: the day-before text at nine in the morning stands as the visionary's [V]
  -> boundary
  serves: N1
  touches: D20

D33 2026-10-18 [V] ratifies D28
  resp: every field read from the camera is shown on the card before the browser uses it, and the user may correct it; the assumption stands as the visionary's [V]
  -> boundary
  serves: N1 N2
  touches: D28

D34 2026-10-18 [V] ratifies D29
  resp: the cut order, bill first, then the Buy step, then the day-before text, with identification, the ticket, the Confirm gate and the report never cut, stands as the visionary's [V]
  -> boundary
  serves: N1 N2 N3
  touches: D29

D35 2026-10-18 [V] signs D34
  resp: the visionary read the contract (USER-NEEDS.md, the five feature files, OUT-OF-SCOPE.md) and signed it with no corrections [V]
  -> boundary
  serves: N1
  touches: none

# Demo integration, 2026-10-18 (~04:30 PDT; dates stay UTC-style). The real Los Angeles citation pages were read: the pay-by-web lookup and the online initial-review form each take a citation number and a CAPTCHA before anything else; no plate field. The visionary chose from three options put to them: the CAPTCHA pause, no real citation for the rehearsal, fixture stores for the product demo.

D36 2026-10-18 [I>V]
  pre:   live mode is driving a real page that asks for a CAPTCHA before it will go on, as the Los Angeles lookup and initial-review pages do [I>V]
  trig:  the agent reaches that page [I>V]
  resp:  the agent fills every field it can, the user sees `Type the CAPTCHA in the browser` on the card, and the chore waits for the user to type it in the visible browser and press the page's own button; the agent never solves or bypasses a CAPTCHA, and the wait has no time-out; reopens if a city drops its CAPTCHA or offers an API [I>V]
  -> fence-assumption captcha-typed-by-the-user
  serves: N1 N2
  touches: D9 D26

D37 2026-10-18 [I>V]
  resp: the pages after the Los Angeles CAPTCHA are unconfirmed, because no real citation number was available at the event to walk them; the demo's Pay and Contest steps therefore run against the fixture city site styled after the real one, declared as such, while the real lookup page is shown up to its CAPTCHA; reopens when a real citation is in hand [I>V]
  -> fence-deferred real-pages-after-the-captcha
  serves: N1
  touches: D9 D27 D36

D38 2026-10-18 [V]
  resp: the product demo runs against the three fixture stores styled after Target, Walmart and Amazon, declared as fixtures, because Target and Walmart refuse automated browsers; the live store search is deferred [V]
  -> fence-deferred live-stores
  serves: N1
  touches: D16 D18
