// features/identify.feature: the thing held up is named within five seconds and
// its chore begins in a visible browser (D4); what cannot be read gets "Hold it
// closer" and no chore (D5); one clock decides between them; a product whose
// size the frame does not settle is asked about before any store is searched,
// and the answer is what the first store is searched for (D8).
//
// A product's chore opens one tab per store (D16), Target first; no store lists
// anything here (no prices are set), so each tab stays on its search results.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import type { BrowserView } from '../harness/app.ts'
import {
  FIXTURES,
  IDENTIFY_SECONDS,
  KINDS,
  cardWithinFive,
  holdUp,
  imageOf,
  imageWith,
  openApp,
  path,
  required,
  show,
  sinceHeld,
  toSecondsAfterFrame,
  type World,
} from './desk.ts'

const HOLD_IT_CLOSER = 'Hold it closer'

/** The fields a row names, against the card's fields, per kind. */
function expectFields(kind: string, named: string, fields: Record<string, string | null>): void {
  let m: RegExpMatchArray | null
  if (kind === 'ticket' && (m = named.match(/^citation (\d+), plate (\w+), ([^,]+), due (\S+)$/))) {
    expect({ citation: fields.citation, plate: fields.plate, city: fields.city, due: fields.due }).toEqual({ citation: m[1], plate: m[2], city: m[3], due: m[4] })
  } else if (kind === 'bill' && (m = named.match(/^(\w+), \$([\d.]+), due (\S+), account (\d+)$/))) {
    expect({ biller: fields.biller, amount: fields.amount, due: fields.due, account: fields.account }).toEqual({ biller: m[1], amount: m[2], due: m[3], account: m[4] })
  } else if (kind === 'product' && (m = named.match(/^(.+), (\d+ oz)$/))) {
    // The card shows the name as the label reads; letter case is the label's typography.
    expect(fields.name?.toLowerCase()).toBe(m[1]!.toLowerCase())
    expect(fields.size).toBe(m[2])
  } else {
    throw new Error(`cannot read the fields "${named}" for a ${kind}`)
  }
}

/** The page a chore opens, as the app's Playwright sees the browser. */
async function expectBrowserOn(w: World, page: string): Promise<void> {
  const app = required(w.app, 'app')
  const view = await app.browser()
  const thing = FIXTURES[required(w.thing, 'thing')]!
  if (page === "the first store's search results") {
    expectFirstStoreSearched(view, String(thing.fields.name), String(thing.fields.size))
    return
  }
  expect(view.tabs, show(view)).toHaveLength(1)
  if (page === 'the Los Angeles pay-or-contest page') {
    expect(path(view)).toBe('/sites/la-citations/lookup')
    expect(view.title).toBe(`City of Los Angeles - Parking Citations - Citation ${thing.fields.citation}`)
    expect({ citation: view.fields.citation, plate: view.fields.plate }).toEqual({ citation: thing.fields.citation, plate: thing.fields.plate })
  } else if (page === 'the LADWP payment page') {
    expect(path(view)).toBe('/sites/ladwp/pay')
    expect(view.title).toMatch(/^LADWP\b.*Pay/i)
  } else {
    throw new Error(`no page "${page}"`)
  }
}

/** The first store's tab (Target's, D16's store order) on its search results for the product, and in front. */
function expectFirstStoreSearched(view: BrowserView, name: string, size: string): void {
  const first = view.tabs[0]
  expect(first, show(view)).toBeDefined()
  const url = new URL(first!.url)
  expect(url.pathname, show(view)).toBe('/sites/target/search')
  expect(first!.title).toMatch(/^Target - Search: /)
  const words = (url.searchParams.get('q') ?? '').toLowerCase().split(/\s+/)
  for (const word of [...name.toLowerCase().split(/\s+/), ...size.toLowerCase().split(/\s+/)]) expect(words, show(view)).toContain(word)
  for (const other of ['12', '32'].filter((n) => !size.startsWith(n))) expect(words, show(view)).not.toContain(other)
  expect(view.url).toBe(first!.url)
}

async function expectNoBrowser(w: World): Promise<void> {
  const app = required(w.app, 'app')
  expect(await app.browser()).toEqual({ url: null, title: null, fields: {}, tabs: [] })
}

const identify: Definer<World> = (reg) => {
  reg.define(/^the Handled web app is open on the laptop with the webcam live and nothing in front of it$/, async (w) => {
    await openApp(w)
  })

  reg.define(/^the user holds (.+) up to the webcam$/, async (w, thing) => {
    await holdUp(w, imageOf(String(thing), w))
  })

  reg.define(/^within 5 seconds the user sees a card naming it (a parking ticket|a bill|a product) with (.+)$/, async (w, kind, fields) => {
    const desk = await cardWithinFive(w)
    expect(desk.identified?.kind).toBe(KINDS[String(kind)])
    expect(desk.notice).toBeNull()
    expectFields(KINDS[String(kind)]!, String(fields), desk.identified!.fields)
  })

  reg.define(/^the user sees a browser window open on (.+)$/, async (w, page) => {
    await expectBrowserOn(w, String(page))
  })

  // "After 5 seconds": not before. At 4.9 s the card does not yet say "Hold it closer";
  // at 5 s it shows the outcome.
  reg.define(/^after 5 seconds the user sees (.+) on the card$/, async (w, outcome) => {
    const app = required(w.app, 'app')
    await toSecondsAfterFrame(w, IDENTIFY_SECONDS - 0.1)
    expect((await app.desk()).notice, `"${HOLD_IT_CLOSER}" ${sinceHeld(w)} s after the frame`).not.toBe(HOLD_IT_CLOSER)
    await toSecondsAfterFrame(w, IDENTIFY_SECONDS)
    const desk = await app.desk()
    if (outcome === `"${HOLD_IT_CLOSER}"`) {
      expect(desk.notice).toBe(HOLD_IT_CLOSER)
      expect(desk.identified, show(desk)).toBeNull()
    } else if (outcome === 'a card naming it a parking ticket') {
      expect(desk.identified?.kind, show(desk)).toBe('ticket')
      expect(desk.notice).toBeNull()
    } else {
      throw new Error(`no outcome ${String(outcome)}`)
    }
  })

  // No window now, and none when a late answer from the eye arrives after the five seconds.
  reg.define(/^the user sees no browser window open$/, async (w) => {
    const app = required(w.app, 'app')
    await expectNoBrowser(w)
    await toSecondsAfterFrame(w, Math.max(sinceHeld(w), w.eyeDelay ?? 0) + 30)
    await expectNoBrowser(w)
    expect((await app.desk()).identified).toBeNull()
  })

  reg.define(/^the eye needs ([\d.]+) seconds? to make out (a Los Angeles parking ticket for citation \d+ on plate \w+)$/, async (w, seconds, thing) => {
    w.eyeDelay = Number(seconds)
    w.thing = imageOf(String(thing), w)
    await required(w.app, 'app').eyeDelay(w.eyeDelay)
  })

  // --- D8 ---------------------------------------------------------------------------
  const hidden = () => imageWith('product', { name: 'Cholula Original hot sauce', size: null })

  reg.define(/^the user holds a bottle of Cholula Original hot sauce up to the webcam with its size hidden by their hand$/, async (w) => {
    await holdUp(w, hidden())
  })

  reg.define(/^the user sees the question "([^"]*)" on the card$/, async (w, question) => {
    const desk = await cardWithinFive(w)
    expect(desk.question).toBe(String(question))
    expect(desk.identified?.fields.size).toBeNull()
  })

  reg.define(/^the card is asking "([^"]*)"$/, async (w, question) => {
    await holdUp(w, hidden())
    expect((await cardWithinFive(w)).question).toBe(String(question))
  })

  reg.define(/^the user says "([^"]*)"$/, async (w, text) => {
    const res = await required(w.app, 'app').say(String(text))
    expect(res.status, await res.clone().text()).toBe(200)
  })

  // No tab opens while the question waits, however long; the answer opens the stores,
  // the first searched for the size the frame suggested.
  reg.define(/^the user sees no store searched until they answer$/, async (w) => {
    const app = required(w.app, 'app')
    await expectNoBrowser(w)
    await app.advance(600)
    await expectNoBrowser(w)
    const desk = await app.desk()
    expect(desk.question, show(desk)).toBe('Is this the 32 oz?')
    expect(desk.ranking).toEqual([])
    expect(desk.not_found).toEqual([])
    const res = await app.say('yes')
    expect(res.status, await res.clone().text()).toBe(200)
    expectFirstStoreSearched(await app.browser(), String(desk.identified?.fields.name), '32 oz')
  })

  reg.define(/^the user sees the first store searched for the (\d+ oz) bottle$/, async (w, size) => {
    const app = required(w.app, 'app')
    const desk = await app.desk()
    expectFirstStoreSearched(await app.browser(), String(desk.identified?.fields.name), String(size))
  })

  reg.define(/^the user sees the card name the product as "([^"]*), (\d+ oz)"$/, async (w, name, size) => {
    const desk = await required(w.app, 'app').desk()
    expect(desk.question).toBeNull()
    expect(desk.identified?.fields.name?.toLowerCase()).toBe(String(name).toLowerCase())
    expect(desk.identified?.fields.size).toBe(String(size))
  })
}

export default identify
