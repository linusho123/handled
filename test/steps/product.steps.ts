// features/product.feature: the product held up is searched at three stores,
// each in its own tab, and the card ranks the prices each store's own product
// page shows, cheapest first, with Buy on the cheapest and a tie in store order
// (D16); a store that does not list it is marked "not found", and with none
// found there is no Buy (D17); Buy reaches the store's checkout with the
// product in the cart, the address on file and the test Visa filled, and
// pauses at Place order (D18); Confirm places the order (D7).
//
// The far side: the card is GET /desk (what the page renders), the tabs and the
// checkout are the browser as the app's Playwright sees it (GET /test/browser:
// each tab's url and title, the active tab's filled fields and visible text),
// and an order is the store's ledger (GET /test/sites/<store>/ledger), written
// only by the fixture store's own Place order route. The prices are set on the
// fixture stores' pages (POST /test/sites); the app reads them from the DOM.
//
// The Background's bottle is "held up" as the scenario's precondition; its frame
// reaches the app when the product chore begins (the When), so the prices and
// listings a scenario sets (Given) are in place before any store is searched.
import { expect } from 'vitest'
import type { Definer } from 'gherkin-node-test/vitest'
import { imageWith, openApp, required, show } from './desk.ts'
import {
  STORES,
  SHIP_TO,
  expectBuyOn,
  expectCheckout,
  expectRanking,
  heldProduct,
  lists,
  productChoreBegins,
  site,
  storeLedgers,
  type StoreWorld,
} from './stores.ts'

type World = StoreWorld & {
  /** The store the scenario made cheapest ("Walmart"); its price is in prices. */
  cheapest?: 'Target' | 'Walmart' | 'Amazon'
}

const list = (names: string) => names.split(/\s*,\s*/)

async function ok(res: Response): Promise<void> {
  expect(res.status, await res.clone().text()).toBe(200)
}

async function expectConfirmOnly(w: World, store: string, price: string): Promise<void> {
  const desk = await required(w.app, 'app').desk()
  expect(desk.controls, show(desk)).toEqual(['Confirm'])
  expect(desk.buy).toBeNull()
  // Paused, the card reports what is waiting (D19), never that it is ordered.
  expect(desk.done).toBe(`Ready to order from ${store}, $${price}, waiting for you`)
}

async function expectNoOrders(w: World): Promise<void> {
  expect(await storeLedgers(w)).toEqual({ Target: [], Walmart: [], Amazon: [] })
}

/** Target $9.49, Walmart at the price given, Amazon $10.99: the D16 outline's first row. */
async function walmartCheapest(w: World, price: string): Promise<void> {
  expect(Number(price)).toBeLessThan(9.49)
  w.cheapest = 'Walmart'
  await lists(w, 'Target', '9.49')
  await lists(w, 'Walmart', price)
  await lists(w, 'Amazon', '10.99')
  await productChoreBegins(w)
  await expectRanking(w, ['Walmart', 'Target', 'Amazon'], [])
  await expectBuyOn(w, 'Walmart')
}

const product: Definer<World> = (reg) => {
  reg.define(/^the Handled web app is open on the laptop with the webcam live$/, async (w) => {
    const app = await openApp(w)
    expect(await app.texts()).toEqual([])
    await expectNoOrders(w)
  })

  reg.define(/^the user has held up a (\d+ oz) bottle of (.+)$/, async (w, size, name) => {
    w.thing = imageWith('product', { name: String(name), size: String(size) })
  })

  // --- D16 -------------------------------------------------------------------------

  reg.define(/^(Target|Walmart|Amazon) lists the (\d+ oz) Cholula Original at \$([\d.]+)$/, async (w, store, size, price) => {
    heldProduct(w, String(size))
    await lists(w, String(store), String(price))
  })

  reg.define(/^(Target|Walmart|Amazon) lists it at \$([\d.]+)$/, async (w, store, price) => {
    await lists(w, String(store), String(price))
  })

  reg.define(/^the product chore begins$/, async (w) => {
    await productChoreBegins(w)
  })

  reg.define(/^the user sees three browser tabs, one per store, each on the product's page$/, async (w) => {
    const view = await required(w.app, 'app').browser()
    const product = heldProduct(w)
    expect(view.tabs, show(view)).toHaveLength(STORES.length)
    expect(view.tabs.map((t) => new URL(t.url).pathname)).toEqual(STORES.map((s) => `/sites/${site(s)}/product/${product.slug}`))
    expect(view.tabs.map((t) => t.title)).toEqual(STORES.map((s) => `${s} - ${product.name}`))
  })

  reg.define(/^the user sees the card rank the stores (.+)$/, async (w, ranking) => {
    await expectRanking(w, list(String(ranking)), [])
  })

  reg.define(/^the user sees the Buy control on (Target|Walmart|Amazon)$/, async (w, store) => {
    await expectBuyOn(w, String(store))
  })

  // --- D17 -------------------------------------------------------------------------

  reg.define(/^(Target|Walmart|Amazon) does not list it$/, async (w, store) => {
    await required(w.app, 'app').setSite(site(String(store)), { fault: 'nolisting' })
  })

  reg.define(/^the user sees the card rank (\w+) then (\w+) with (\w+) marked "not found"$/, async (w, first, second, missing) => {
    await expectRanking(w, [String(first), String(second)], [String(missing)])
    // The store that does not list it is not searched past its results: its tab stays there.
    const view = await required(w.app, 'app').browser()
    const tab = view.tabs[STORES.indexOf(String(missing) as (typeof STORES)[number])]
    expect(new URL(tab?.url ?? 'about:blank').pathname, show(view)).toBe(`/sites/${site(String(missing))}/search`)
  })

  reg.define(/^none of (\w+), (\w+) and (\w+) lists the (\d+ oz) Cholula Original$/, async (w, a, b, c, size) => {
    heldProduct(w, String(size))
    for (const store of [a, b, c]) await required(w.app, 'app').setSite(site(String(store)), { fault: 'nolisting' })
  })

  // A line the card shows: the failed step, what was done.
  reg.define(/^the user sees on the card "([^"]*)"$/, async (w, text) => {
    const desk = await required(w.app, 'app').desk()
    const lines = [desk.failed_step, desk.done, desk.notice, desk.question]
    expect(lines, show(desk)).toContain(String(text))
  })

  reg.define(/^the user sees no Buy control$/, async (w) => {
    const app = required(w.app, 'app')
    const desk = await app.desk()
    expect(desk.controls, show(desk)).toEqual([])
    expect(desk.buy).toBeNull()
    expect(desk.ranking).toEqual([])
    expect(desk.not_found).toEqual([...STORES])
    // Nothing on the card takes a Buy, and nothing is ordered anywhere.
    expect((await app.tap('Buy')).status).toBe(409)
    await expectNoOrders(w)
  })

  // --- D18 -------------------------------------------------------------------------

  reg.define(/^the card ranks Walmart cheapest at \$([\d.]+) with the Buy control on it$/, async (w, price) => {
    await walmartCheapest(w, String(price))
  })

  reg.define(/^the user taps Buy$/, async (w) => {
    await ok(await required(w.app, 'app').tap('Buy'))
  })

  reg.define(/^the user sees the browser on (Target|Walmart|Amazon)'s checkout with the (\d+ oz) Cholula Original in the cart, the shipping address filled and the Visa on file filled$/, async (w, store, size) => {
    heldProduct(w, String(size))
    await expectCheckout(w, String(store))
  })

  reg.define(/^the user sees the Confirm control on the card$/, async (w) => {
    // The store and price the scenario set (the Given), never the app's own ranking.
    const store = required(w.cheapest, 'cheapest')
    await expectConfirmOnly(w, store, required(required(w.prices, 'prices')[store], `price at ${store}`))
    const desk = await required(w.app, 'app').desk()
    const view = await required(w.app, 'app').browser()
    expect(desk.link).toBe(view.url)
  })

  reg.define(/^Walmart's records show no order placed$/, async (w) => {
    await expectNoOrders(w)
  })

  // --- D7 --------------------------------------------------------------------------

  reg.define(/^the browser is paused on Walmart's checkout with the Confirm control showing$/, async (w) => {
    await walmartCheapest(w, '8.98')
    await ok(await required(w.app, 'app').tap('Buy'))
    await expectCheckout(w, 'Walmart')
    await expectConfirmOnly(w, 'Walmart', '8.98')
    await expectNoOrders(w)
  })

  reg.define(/^the user taps Confirm$/, async (w) => {
    await ok(await required(w.app, 'app').confirm())
  })

  reg.define(/^Walmart's records show one order for the (\d+ oz) Cholula Original$/, async (w, size) => {
    const product = heldProduct(w, String(size))
    const price = required(w.prices, 'prices').Walmart!
    expect(await storeLedgers(w)).toEqual({
      Target: [],
      Walmart: [{ kind: 'order', items: [{ slug: product.slug, name: product.name, price }], total: price, ship_to: SHIP_TO, card_last4: '4242' }],
      Amazon: [],
    })
  })
}

export default product
