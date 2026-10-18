// features/ticket.feature: the city's pay-or-contest page filled, Pay or Contest
// on the card (D9); a failed step submits nothing (D10); Pay and Contest pause
// at Confirm (D11, D12); Confirm, tapped or said, completes the step (D7);
// walking away leaves it paused forever (D6); no printed due date means
// twenty-one days from the printed issue date (D13).
//
// The Background's ticket is "held up" as the scenario's precondition; its frame
// reaches the app when the ticket chore begins (the When), so a fault a scenario
// sets on the city's page (Given) is in place before the chore touches it.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import {
  CARD_ON_FILE_DIGITS,
  FIXTURES,
  cardWithinFive,
  cityRecords,
  holdUp,
  imageWith,
  openApp,
  path,
  required,
  show,
  type World,
} from './desk.ts'

/** The reason the user gives out loud (D12), as the cassette recorded it. */
const REASON = 'the meter was broken, I put in two dollars and it never started'
const CITY_TITLE = 'City of Los Angeles - Parking Citations'

const citationOf = (w: World) => String(FIXTURES[required(w.thing, 'thing')]!.fields.citation)

async function chorebegins(w: World): Promise<void> {
  await holdUp(w, required(w.thing, 'thing'))
  await cardWithinFive(w)
}

async function expectPayOrContestPage(w: World, citation: string, plate: string): Promise<void> {
  const view = await required(w.app, 'app').browser()
  expect(path(view), show(view)).toBe('/sites/la-citations/lookup')
  expect(view.title).toBe(`${CITY_TITLE} - Citation ${citation}`)
  expect({ citation: view.fields.citation, plate: view.fields.plate }).toEqual({ citation, plate })
}

async function expectPaymentPage(w: World, amount: string): Promise<void> {
  const view = await required(w.app, 'app').browser()
  expect(path(view), show(view)).toBe('/sites/la-citations/pay')
  expect(view.title).toBe(`${CITY_TITLE} - Pay citation ${citationOf(w)}`)
  expect(view.fields.card_number?.replace(/\D/g, '')).toBe(CARD_ON_FILE_DIGITS)
  expect(view.fields.card_expiry).toMatch(/^\d{2}\/\d{2}$/)
  expect(view.fields.card_cvc).toMatch(/^\d{3,4}$/)
  expect(view.fields.card_name).not.toBe('')
  expect(view.fields.amount).toBe(`$${amount}`)
}

async function expectConfirmOnly(w: World): Promise<void> {
  const desk = await required(w.app, 'app').desk()
  expect(desk.controls, show(desk)).toEqual(['Confirm'])
  expect(desk.done).toBeNull()
}

async function tap(w: World, control: string): Promise<void> {
  const res = await required(w.app, 'app').tap(control)
  expect(res.status, await res.clone().text()).toBe(200)
}

async function say(w: World, text: string): Promise<void> {
  const res = await required(w.app, 'app').say(text)
  expect(res.status, await res.clone().text()).toBe(200)
}

async function pageFilled(w: World): Promise<void> {
  await chorebegins(w)
  const ticket = FIXTURES[required(w.thing, 'thing')]!
  await expectPayOrContestPage(w, String(ticket.fields.citation), String(ticket.fields.plate))
  expect((await required(w.app, 'app').desk()).controls).toEqual(['Pay', 'Contest'])
}

async function contestLetter(w: World): Promise<void> {
  const desk = await required(w.app, 'app').desk()
  const letter = desk.letter
  expect(letter, show(desk)).toBeTruthy()
  expect(letter).not.toMatch(/\n/)
  expect(letter).toMatch(/\bmeter\b/i)
  expect(letter).toMatch(/\bbroken\b/i)
  expect(letter).toMatch(/\btwo dollars\b|\$2(\.00)?\b/i)
  w.letter = letter!
}

async function contestForm(w: World): Promise<void> {
  const app = required(w.app, 'app')
  const view = await app.browser()
  expect(path(view), show(view)).toBe('/sites/la-citations/contest')
  expect(view.title).toBe(`${CITY_TITLE} - Contest citation ${citationOf(w)}`)
  expect(view.fields.letter).toBe(required(w.letter, 'letter'))
}

const SECONDS: Record<string, number> = { minute: 60, hour: 3600, day: 86400 }

const ticket: Definer<World> = (reg) => {
  reg.define(/^the Handled web app is open on the laptop with the webcam live$/, async (w) => {
    await openApp(w)
  })

  reg.define(/^the user has held up a Los Angeles parking ticket for citation (\d+) on plate (\w+) issued (\S+) and due (\S+)$/, async (w, citation, plate, issued, due) => {
    w.thing = imageWith('ticket', { city: 'Los Angeles', citation: String(citation), plate: String(plate), issued: String(issued), due: String(due) })
  })

  reg.define(/^the user has held up a Los Angeles parking ticket for citation (\d+) issued (\S+) with no due date printed$/, async (w, citation, issued) => {
    w.thing = imageWith('ticket', { city: 'Los Angeles', citation: String(citation), issued: String(issued), due: null })
  })

  reg.define(/^the ticket chore begins$/, async (w) => {
    await chorebegins(w)
  })

  reg.define(/^the user sees the browser on the Los Angeles pay-or-contest page with citation (\d+) and plate (\w+) filled in$/, async (w, citation, plate) => {
    await expectPayOrContestPage(w, String(citation), String(plate))
  })

  reg.define(/^the user sees the card offer "Pay" and "Contest" with the deadline (\S+)$/, async (w, deadline) => {
    const desk = await required(w.app, 'app').desk()
    expect(desk.controls, show(desk)).toEqual(['Pay', 'Contest'])
    expect(desk.deadline).toBe(String(deadline))
  })

  reg.define(/^the city's page does not answer$/, async (w) => {
    await required(w.app, 'app').setSite('la-citations', { fault: 'down' })
  })

  reg.define(/^the city's page finds no citation (\d+)$/, async (w, citation) => {
    expect(String(citation)).toBe(citationOf(w))
    await required(w.app, 'app').setSite('la-citations', { fault: 'notfound' })
  })

  reg.define(/^the city's page demands a login before showing the citation$/, async (w) => {
    await required(w.app, 'app').setSite('la-citations', { fault: 'login' })
  })

  // A line the card shows: the failed step, what was done, how the deadline was counted.
  reg.define(/^the user sees on the card "([^"]*)"$/, async (w, text) => {
    const desk = await required(w.app, 'app').desk()
    const lines = [desk.failed_step, desk.done, desk.deadline_note, desk.notice, desk.question]
    expect(lines, show(desk)).toContain(String(text))
  })

  reg.define(/^the user sees the browser still open on (.+)$/, async (w, page) => {
    const app = required(w.app, 'app')
    const view = await app.browser()
    expect(view.tabs, show(view)).toHaveLength(1)
    if (page === 'the blank tab it tried to open') {
      expect(view.url).toBe(`${app.url}/sites/la-citations/`)
      expect(view.title).toBe('')
      expect(view.fields).toEqual({})
    } else if (page === "the city's lookup page") {
      expect(path(view)).toBe('/sites/la-citations/lookup')
      expect(view.title).toBe(`${CITY_TITLE} - Look up a citation`)
    } else if (page === "the city's login page") {
      expect(path(view)).toBe('/sites/la-citations/login')
      expect(view.title).toBe(`${CITY_TITLE} - Sign in`)
      expect(Object.keys(view.fields).sort()).toEqual(['password', 'username'])
      expect(view.fields).toEqual({ username: '', password: '' })
    } else {
      throw new Error(`no page "${String(page)}"`)
    }
  })

  reg.define(/^the city's records show nothing submitted for citation (\d+)$/, async (w, citation) => {
    expect(await cityRecords(w, String(citation))).toEqual([])
  })

  reg.define(/^the pay-or-contest page is filled$/, async (w) => {
    await pageFilled(w)
  })

  reg.define(/^the user taps "(Pay|Contest)"$/, async (w, control) => {
    await tap(w, String(control))
  })

  reg.define(/^the user sees the browser on the city's payment page with the card on file filled in and the amount \$([\d.]+)$/, async (w, amount) => {
    await expectPaymentPage(w, String(amount))
  })

  reg.define(/^the user sees the Confirm control on the card$/, async (w) => {
    await expectConfirmOnly(w)
  })

  reg.define(/^the city's records show nothing paid for citation (\d+)$/, async (w, citation) => {
    expect(await cityRecords(w, String(citation), 'payment')).toEqual([])
  })

  reg.define(/^the user taps "Contest" and says "([^"]*)"$/, async (w, reason) => {
    await tap(w, 'Contest')
    await say(w, String(reason))
  })

  reg.define(/^the user sees on the card a one-paragraph letter that mentions the broken meter and the two dollars$/, async (w) => {
    await contestLetter(w)
  })

  reg.define(/^the user sees the browser on the city's contest form with that letter pasted in$/, async (w) => {
    await contestForm(w)
  })

  reg.define(/^the city's records show no contest filed for citation (\d+)$/, async (w, citation) => {
    expect(await cityRecords(w, String(citation), 'contest')).toEqual([])
  })

  reg.define(/^the browser is paused on the city's payment page with the Confirm control showing$/, async (w) => {
    await pageFilled(w)
    await tap(w, 'Pay')
    await expectPaymentPage(w, '73.00')
    await expectConfirmOnly(w)
    expect(await cityRecords(w, citationOf(w))).toEqual([])
  })

  reg.define(/^the browser is paused on the city's contest form with the Confirm control showing$/, async (w) => {
    await pageFilled(w)
    await tap(w, 'Contest')
    await say(w, REASON)
    await contestLetter(w)
    await contestForm(w)
    await expectConfirmOnly(w)
    expect(await cityRecords(w, citationOf(w))).toEqual([])
  })

  reg.define(/^the user taps Confirm$/, async (w) => {
    const res = await required(w.app, 'app').confirm()
    expect(res.status, await res.clone().text()).toBe(200)
  })

  reg.define(/^the user says "([^"]*)"$/, async (w, text) => {
    await say(w, String(text))
  })

  reg.define(/^the city's records show citation (\d+) paid$/, async (w, citation) => {
    const paid = await cityRecords(w, String(citation), 'payment')
    expect(paid).toEqual([{ kind: 'payment', citation: String(citation), amount: '73.00', card_last4: CARD_ON_FILE_DIGITS.slice(-4), card_name: expect.any(String) }])
  })

  reg.define(/^the city's records show a contest filed for citation (\d+)$/, async (w, citation) => {
    expect(await cityRecords(w, String(citation), 'contest')).toEqual([{ kind: 'contest', citation: String(citation), letter: required(w.letter, 'letter') }])
  })

  reg.define(/^(\d+) (minute|hour|day)s? passes? with no tap and no word from the user$/, async (w, n, unit) => {
    await required(w.app, 'app').advance(Number(n) * SECONDS[String(unit)]!)
  })

  reg.define(/^the user sees the browser still paused on the city's payment page with the Confirm control showing$/, async (w) => {
    await expectPaymentPage(w, '73.00')
    await expectConfirmOnly(w)
  })
}

export default ticket
