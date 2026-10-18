// features/bill.feature: the bill's payment page found, the account number and
// the amount filled, paused before paying with Confirm showing (D14, D7); no
// payment page found, a page that does not answer, or a login wall pays nothing
// and the card shows "call to pay" with the phone number the bill prints (D15,
// D26); Confirm pays it and the card says so (D7).
//
// The far side: the card is GET /desk (what the page renders); the browser is
// the app's Playwright view (GET /test/browser: the tab's url, title and the
// field values in its DOM); the biller's records are the fixture biller's own
// ledger (GET /test/sites/ladwp/ledger), written only by its pay route when a
// form posts to it. The fixture biller's pages print the site's own customer
// service number, never the bill's, so a card that read its number from a page
// shows the wrong one.
//
// The Background's bill is "held up" as the scenario's precondition; its frame
// reaches the app when the bill chore begins (the When), so a fault a scenario
// sets on the biller's page (Given) is in place before the chore touches it.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import type { App, BrowserView } from '../harness/app.ts'
import { CARD_ON_FILE_DIGITS, FIXTURES, cardWithinFive, holdUp, imageWith, openApp, path, required, show, type World } from './desk.ts'

const BILLER_TITLE = 'LADWP - Los Angeles Department of Water and Power'

/** A field the held-up bill prints, as make-images.py drew it. */
const printed = (w: World, field: string) => String(FIXTURES[required(w.thing, 'thing')]!.fields[field])

async function billChoreBegins(w: World): Promise<void> {
  await holdUp(w, required(w.thing, 'thing'))
  await cardWithinFive(w)
}

/** The bare amount a form field holds ("$148.22" or "148.22" → "148.22"). */
const bare = (value: string | undefined) => (value ?? '').trim().replace(/^\$/, '')

async function expectPaymentPage(app: App, account: string, amount: string): Promise<BrowserView> {
  const view = await app.browser()
  expect(path(view), show(view)).toBe('/sites/ladwp/pay')
  expect(view.title).toBe(`${BILLER_TITLE} - Pay my bill`)
  expect(view.fields.account).toBe(account)
  expect(bare(view.fields.amount)).toBe(amount)
  return view
}

async function expectConfirmOnly(app: App, amount: string): Promise<void> {
  const desk = await app.desk()
  expect(desk.controls, show(desk)).toEqual(['Confirm'])
  // Paused, the card reports what is waiting (D19), never that it is paid.
  expect(desk.done).toBe(`Ready to pay LADWP $${amount}, waiting for you`)
  expect(desk.failed_step).toBeNull()
  expect(desk.call_to_pay).toBeNull()
}

async function billerRecords(app: App, account: string) {
  return (await app.ledger('ladwp')).filter((e) => e.account === account)
}

const bill: Definer<World> = (reg) => {
  reg.define(/^the Handled web app is open on the laptop with the webcam live$/, async (w) => {
    await openApp(w)
  })

  reg.define(
    /^the user has held up an LADWP bill for \$([\d.]+) due (\S+) on account (\d+) with the phone number (\S+) printed on it$/,
    async (w, amount, due, account, phone) => {
      w.thing = imageWith('bill', { biller: 'LADWP', amount: String(amount), due: String(due), account: String(account), phone: String(phone) })
    },
  )

  reg.define(/^the bill chore begins$/, async (w) => {
    await billChoreBegins(w)
  })

  // --- D14 -------------------------------------------------------------------------

  reg.define(/^the user sees the browser on the LADWP payment page with account (\d+) and the amount \$([\d.]+) filled in$/, async (w, account, amount) => {
    const app = required(w.app, 'app')
    const view = await expectPaymentPage(app, String(account), String(amount))
    // The card on file is filled too, so Confirm alone can pay (D7).
    expect(view.fields.card_number?.replace(/\D/g, ''), show(view)).toBe(CARD_ON_FILE_DIGITS)
    expect(view.tabs).toHaveLength(1)
    expect((await app.desk()).link).toBe(view.url)
  })

  reg.define(/^the user sees the Confirm control on the card$/, async (w) => {
    await expectConfirmOnly(required(w.app, 'app'), printed(w, 'amount'))
  })

  reg.define(/^the user sees on the card (\w+), \$([\d.]+) and the due date (\d{4}-\d{2}-\d{2})$/, async (w, biller, amount, due) => {
    const desk = await required(w.app, 'app').desk()
    expect(desk.identified?.kind, show(desk)).toBe('bill')
    expect(desk.identified?.fields.biller).toBe(String(biller))
    expect(desk.identified?.fields.amount).toBe(String(amount))
    expect(desk.identified?.fields.due).toBe(String(due))
    expect(desk.deadline).toBe(String(due))
  })

  reg.define(/^the biller's records show nothing paid on account (\d+)$/, async (w, account) => {
    expect(await billerRecords(required(w.app, 'app'), String(account))).toEqual([])
  })

  // --- D15 -------------------------------------------------------------------------

  reg.define(/^no payment page for LADWP can be found$/, async (w) => {
    await required(w.app, 'app').setSite('ladwp', { fault: 'nopage' })
  })

  reg.define(/^the LADWP payment page does not answer$/, async (w) => {
    await required(w.app, 'app').setSite('ladwp', { fault: 'down' })
  })

  reg.define(/^the LADWP payment page demands a login$/, async (w) => {
    await required(w.app, 'app').setSite('ladwp', { fault: 'login' })
  })

  reg.define(/^the user sees on the card "call to pay" with (\S+)$/, async (w, phone) => {
    const desk = await required(w.app, 'app').desk()
    // The number the bill prints, as the eye read it: never one a page shows.
    expect(desk.identified?.fields.phone, show(desk)).toBe(String(phone))
    expect(desk.call_to_pay).toBe(String(phone))
    expect(desk.failed_step).not.toBeNull()
    expect(desk.done).toBe(`${desk.failed_step}: call to pay ${String(phone)}`)
    expect(desk.controls).toEqual([])
  })

  reg.define(/^the user sees the browser still open on (.+)$/, async (w, page) => {
    const app = required(w.app, 'app')
    const view = await app.browser()
    expect(view.tabs, show(view)).toHaveLength(1)
    if (page === 'the search results it tried') {
      expect(path(view), show(view)).toBe('/sites/ladwp/search')
      expect(view.title).toBe(`${BILLER_TITLE} - Search results`)
      expect(new URL(view.url!).searchParams.get('q')).toMatch(/\bpay\b/i)
    } else if (page === 'the blank tab it tried to open') {
      expect(view.url).toBe(`${app.url}/sites/ladwp/pay`)
      expect(view.title).toBe('')
      expect(view.fields).toEqual({})
    } else if (page === "the biller's login page") {
      expect(path(view), show(view)).toBe('/sites/ladwp/login')
      expect(view.title).toBe(`${BILLER_TITLE} - Sign in`)
      expect(view.fields).toEqual({ username: '', password: '' })
    } else {
      throw new Error(`no page "${String(page)}"`)
    }
    expect((await app.desk()).link).toBe(view.url)
  })

  // --- D7 --------------------------------------------------------------------------

  reg.define(/^the browser is paused on the LADWP payment page with the Confirm control showing$/, async (w) => {
    const app = required(w.app, 'app')
    await billChoreBegins(w)
    await expectPaymentPage(app, printed(w, 'account'), printed(w, 'amount'))
    await expectConfirmOnly(app, printed(w, 'amount'))
    expect(await app.ledger('ladwp')).toEqual([])
  })

  reg.define(/^the user taps Confirm$/, async (w) => {
    const res = await required(w.app, 'app').confirm()
    expect(res.status, await res.clone().text()).toBe(200)
  })

  reg.define(/^the biller's records show \$([\d.]+) paid on account (\d+)$/, async (w, amount, account) => {
    const paid = await billerRecords(required(w.app, 'app'), String(account))
    expect(paid).toEqual([{ kind: 'payment', account: String(account), amount: String(amount), card_last4: CARD_ON_FILE_DIGITS.slice(-4), card_name: expect.any(String) }])
  })

  reg.define(/^the user sees on the card "([^"]*)"$/, async (w, text) => {
    const desk = await required(w.app, 'app').desk()
    expect(desk.done, show(desk)).toBe(String(text))
    expect(desk.controls).toEqual([])
  })
}

export default bill
