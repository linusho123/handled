// features/report.feature: every chore end (completed after Confirm, paused at
// Confirm, stopped at a failed step) puts what was identified, what was done,
// the deadline and a link to the page on the card, and sends exactly one text
// with the same (D19); a deadline brings a second text at nine in the morning
// the day before it (D20, ratified D32); a product gets none (D21).
//
// The far side: the card is GET /desk (what the page renders), the link is
// checked against the browser as the app's Playwright sees it (GET
// /test/browser), and the phone is the texts fake's capture (GET /test/texts),
// each text stamped with the app's virtual clock when it was sent. No step waits
// real time: the clock moves only through POST /test/advance.
//
// Held in the wip register (test/features.test.ts): the D19 rows whose chore
// ends are built later (the LADWP bill paused at Confirm on its payment page,
// P4; the Cholula order from Walmart, P3). Their distinguishing steps stay
// unbound. D21 is bound through the product chore's end before P3: its failed
// step, the first store's page not answering, reported with no deadline.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import { cardWithinFive, holdUp, imageWith, openApp, required, show, type World as DeskWorld } from './desk.ts'

type World = DeskWorld & {
  /** How the chore is to end (the D19 outline's "ended" column). */
  ending?: string
  /** Texts the phone had received before the end the scenario is about. */
  textsBefore?: number
  /** The deadline the chore was reported with (D20). */
  deadline?: string
  /** The texts the phone had one second before nine on the day before (D20). */
  textsJustBeforeNine?: number
  /** The virtual time the D20 clock was moved to (local ISO). */
  nine?: string
  /** The one text the product chore's end sent (D21). */
  firstText?: { body: string; at: string }
  /** The virtual time the product chore was reported at (D21). */
  reportedAt?: string
}

/** D21: the clock walks the thirty days an hour at a time, so a text due at any hour goes on its own tick. */
const DAY = 86400
const HOUR = 3600

const ENDINGS = ['been confirmed as paid', 'paused at Confirm on the payment page', "stopped because the city's page did not answer"] as const

/** 2026-11-02 → "Nov 2, 2026", the date as the text says it. */
const human = (iso: string) => new Date(`${iso}T00:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' })

/** Seconds of virtual time from the app's clock to a local ISO time. */
const secondsUntil = (now: string, at: string) => (Date.parse(`${at}Z`) - Date.parse(`${now}Z`)) / 1000

async function ok(res: Response): Promise<void> {
  expect(res.status, await res.clone().text()).toBe(200)
}

/** The ticket chore begins and the user taps Pay: it pauses at Confirm on the city's payment page. */
async function payAndPause(w: World): Promise<void> {
  const app = required(w.app, 'app')
  await holdUp(w, required(w.thing, 'thing'))
  await cardWithinFive(w)
  await ok(await app.tap('Pay'))
  const desk = await app.desk()
  expect(desk.controls, show(desk)).toEqual(['Confirm'])
  expect(await app.ledger('la-citations')).toEqual([])
}

const LADWP_BILL = /^an LADWP bill for \$([\d.]+) due (\S+) on account (\d+)$/
const LA_TICKET = /^a Los Angeles parking ticket for citation (\d+) due (\S+)$/

const report: Definer<World> = (reg) => {
  reg.define(/^the Handled web app is open on the laptop with the webcam live$/, async (w) => {
    const app = await openApp(w)
    expect(await app.texts()).toEqual([])
  })

  // --- D19 -------------------------------------------------------------------------

  reg.define(/^the user has held up a Los Angeles parking ticket for citation (\d+) due (\S+)$/, async (w, citation, due) => {
    w.thing = imageWith('ticket', { city: 'Los Angeles', citation: String(citation), due: String(due) })
  })

  reg.define(/^the chore has (been confirmed as paid|paused at Confirm on the payment page|stopped because the city's page did not answer)$/, async (w, ended) => {
    w.ending = String(ended)
    if (w.ending === ENDINGS[2]) await required(w.app, 'app').setSite('la-citations', { fault: 'down' })
  })

  reg.define(/^the chore ends$/, async (w) => {
    const app = required(w.app, 'app')
    const ending = required(w.ending, 'ending')
    w.textsBefore = (await app.texts()).length
    if (ending === ENDINGS[2]) {
      await holdUp(w, required(w.thing, 'thing'))
      await cardWithinFive(w)
      return
    }
    await payAndPause(w)
    if (ending === ENDINGS[0]) {
      w.textsBefore = (await app.texts()).length
      await ok(await app.confirm())
      expect((await app.ledger('la-citations')).filter((e) => e.kind === 'payment')).toHaveLength(1)
    }
  })

  reg.define(/^the user sees a card with citation (\d+), "([^"]*)", (\d{4}-\d{2}-\d{2}) and a link to the page the browser is on$/, async (w, citation, done, deadline) => {
    const app = required(w.app, 'app')
    const desk = await app.desk()
    expect(desk.identified?.kind, show(desk)).toBe('ticket')
    expect(desk.identified?.fields.citation).toBe(String(citation))
    expect(desk.done).toBe(String(done))
    expect(desk.deadline).toBe(String(deadline))
    const view = await app.browser()
    expect(view.url, show(view)).not.toBeNull()
    expect(desk.link).toBe(view.url)
  })

  reg.define(/^the user's phone receives one text saying "([^"]*)" with (\d{4}-\d{2}-\d{2})$/, async (w, done, deadline) => {
    const app = required(w.app, 'app')
    const texts = await app.texts()
    const fresh = texts.slice(required(w.textsBefore, 'textsBefore'))
    expect(fresh, show(texts)).toHaveLength(1)
    const [text] = fresh
    expect(text!.body).toContain(String(done))
    expect(text!.body).toContain(`Due ${human(String(deadline))}`)
    // Sent at the chore's end, on the app's clock.
    expect(text!.at).toBe(app.now)
  })

  // --- D20 -------------------------------------------------------------------------

  reg.define(/^the user has held up (.+) and the chore was reported with the deadline (\S+)$/, async (w, thing, deadline) => {
    const app = required(w.app, 'app')
    let m: RegExpMatchArray | null
    if ((m = String(thing).match(LA_TICKET))) {
      w.thing = imageWith('ticket', { city: 'Los Angeles', citation: m[1]!, due: m[2]! })
      await payAndPause(w)
    } else if ((m = String(thing).match(LADWP_BILL))) {
      // Any end of D19 reports the deadline; the bill chore's end before P4 is its
      // failed step: the biller's page does not answer.
      w.thing = imageWith('bill', { biller: 'LADWP', amount: m[1]!, due: m[2]!, account: m[3]! })
      await app.setSite('ladwp', { fault: 'down' })
      await holdUp(w, w.thing)
      await cardWithinFive(w)
      const desk = await app.desk()
      expect(desk.failed_step, show(desk)).toBe('Could not reach the LADWP payment page')
    } else {
      throw new Error(`no chore for "${String(thing)}"`)
    }
    const desk = await app.desk()
    expect(desk.deadline, show(desk)).toBe(String(deadline))
    const texts = await app.texts()
    expect(texts, show(texts)).toHaveLength(1)
    expect(texts[0]!.body).toContain(`Due ${human(String(deadline))}`)
    w.deadline = String(deadline)
  })

  reg.define(/^the clock reaches 9:00 in the morning on (\d{4}-\d{2}-\d{2})$/, async (w, day) => {
    const app = required(w.app, 'app')
    const nine = `${String(day)}T09:00:00`
    // The clock walks to one second before nine, then to nine: a text due earlier
    // than nine goes in the first step, stamped then, and the Then sees it.
    const toJustBefore = secondsUntil(app.now, nine) - 1
    expect(toJustBefore, `the clock is already at ${app.now}`).toBeGreaterThan(0)
    await app.advance(toJustBefore)
    w.textsJustBeforeNine = (await app.texts()).length
    await app.advance(1)
    expect(app.now).toBe(nine)
    w.nine = nine
  })

  reg.define(/^the user's phone receives a second text naming (.+) and saying the deadline is tomorrow$/, async (w, chore) => {
    const app = required(w.app, 'app')
    const texts = await app.texts()
    expect(required(w.textsJustBeforeNine, 'textsJustBeforeNine'), show(texts)).toBe(1)
    expect(texts, show(texts)).toHaveLength(2)
    const second = texts[1]!
    expect(second.at).toBe(required(w.nine, 'nine'))
    expect(second.body).toContain(String(chore))
    expect(second.body).toMatch(/\bdeadline\b.*\bis tomorrow\b/)
    expect(second.body).toContain(human(required(w.deadline, 'deadline')))
  })

  // --- D21 -------------------------------------------------------------------------

  reg.define(/^the user has held up a (\d+ oz) bottle of (.+) and the chore was reported with no deadline$/, async (w, size, name) => {
    const app = required(w.app, 'app')
    // The product chore's end before P3 is its failed step: the first store's page does
    // not answer. D19 reports it on the card and in one text, with no deadline.
    await app.setSite('target', { fault: 'down' })
    w.thing = imageWith('product', { name: String(name), size: String(size) })
    await holdUp(w, w.thing)
    await cardWithinFive(w)
    const desk = await app.desk()
    expect(desk.identified?.kind, show(desk)).toBe('product')
    expect(desk.identified?.fields.name?.toLowerCase()).toBe(String(name).toLowerCase())
    expect(desk.identified?.fields.size?.toLowerCase()).toBe(String(size).toLowerCase())
    expect(desk.failed_step, show(desk)).toBe('Could not reach Target')
    expect(desk.done).toBe('Could not reach Target')
    expect(desk.deadline).toBeNull()
    const texts = await app.texts()
    expect(texts, show(texts)).toHaveLength(1)
    expect(texts[0]!.body).toContain('Could not reach Target')
    expect(texts[0]!.body).toContain('No deadline')
    expect(texts[0]!.at).toBe(app.now)
    w.firstText = { body: texts[0]!.body, at: texts[0]!.at }
    w.reportedAt = app.now
  })

  reg.define(/^(\d+) days pass$/, async (w, days) => {
    const app = required(w.app, 'app')
    const from = app.now
    for (let hour = 0; hour < Number(days) * 24; hour++) await app.advance(HOUR)
    expect(secondsUntil(from, app.now)).toBe(Number(days) * DAY)
  })

  reg.define(/^the user's phone receives no second text$/, async (w) => {
    const app = required(w.app, 'app')
    const texts = await app.texts()
    expect(secondsUntil(required(w.reportedAt, 'reportedAt'), app.now), 'the clock has not moved past the report').toBeGreaterThan(0)
    expect(texts.map((t) => ({ body: t.body, at: t.at })), show(texts)).toEqual([required(w.firstText, 'firstText')])
  })
}

export default report
