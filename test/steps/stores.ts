// What the product, identify and report bindings share about the three fixture
// stores (test/sites/fixture_sites/stores.py): their names in store order (the
// ranking's tie order, D16), the catalog slug and name of the product held up,
// the address on file a checkout is filled with (D18), and the far-side reads:
// the stores' tabs as the app's Playwright sees them (GET /test/browser) and
// each store's ledger (GET /test/sites/<store>/ledger), which only its own
// Place order route writes.
import { expect } from 'vitest'
import type { SiteName } from '../harness/app.ts'
import { CARD_ON_FILE_DIGITS, FIXTURES, cardWithinFive, holdUp, required, show, type World } from './desk.ts'

export const STORES = ['Target', 'Walmart', 'Amazon'] as const
export type StoreName = (typeof STORES)[number]

export const site = (store: string): SiteName => {
  if (!(STORES as readonly string[]).includes(store)) throw new Error(`no store ${store}`)
  return store.toLowerCase() as SiteName
}

/** The address on file (app/desk/wallet.py), as a checkout's form holds it and the order records it. */
export const SHIP_TO = { name: 'Handled Test', street: '123 Main St', city: 'Los Angeles', state: 'CA', zip: '90012' }

/** The stores' catalog (test/sites/fixture_sites/stores.py), by the name and size the eye reads. */
const CATALOG: Record<string, { slug: string; name: string }> = {
  'cholula original hot sauce|32 oz': { slug: 'cholula-original-32oz', name: 'Cholula Original Hot Sauce, 32 oz' },
  'cholula original hot sauce|12 oz': { slug: 'cholula-original-12oz', name: 'Cholula Original Hot Sauce, 12 oz' },
}

export function catalogEntry(name: string, size: string): { slug: string; name: string } {
  const entry = CATALOG[`${name.toLowerCase()}|${size.toLowerCase()}`]
  if (!entry) throw new Error(`no catalog product for ${name}, ${size}`)
  return entry
}

/** "Cholula Original" in a step names the product held up; its catalog entry by the fixture's own fields. */
export function heldProduct(w: World, size?: string): { slug: string; name: string } {
  const fixture = FIXTURES[required(w.thing, 'thing')]!
  expect(fixture.kind).toBe('product')
  if (size !== undefined) expect(fixture.fields.size).toBe(size)
  return catalogEntry(String(fixture.fields.name), String(fixture.fields.size))
}

export type StoreWorld = World & {
  /** The price each store lists the product at, as the scenario set it ("8.98"). */
  prices?: Partial<Record<StoreName, string>>
}

/** A store lists the product held up at a price (the fixture store's own page shows it). */
export async function lists(w: StoreWorld, store: string, price: string): Promise<void> {
  const product = heldProduct(w)
  w.prices = { ...w.prices, [store]: price }
  await required(w.app, 'app').setSite(site(store), { prices: { [product.slug]: price } })
}

/** The product chore begins: the frame of the product held up reaches the app, and the card names it. */
export async function productChoreBegins(w: World): Promise<void> {
  await holdUp(w, required(w.thing, 'thing'))
  const desk = await cardWithinFive(w)
  expect(desk.identified?.kind, show(desk)).toBe('product')
}

/** The card's ranking: the stores in order, each with the price its own page listed. */
export async function expectRanking(w: StoreWorld, stores: string[], notFound: string[]): Promise<void> {
  const desk = await required(w.app, 'app').desk()
  expect(desk.ranking.map((r) => r.store), show(desk)).toEqual(stores)
  for (const r of desk.ranking) expect(r.price, show(r)).toBe(`$${required(w.prices, 'prices')[r.store as StoreName]}`)
  expect(desk.not_found, show(desk)).toEqual(notFound)
}

/** The Buy control is on the card, on this store, the cheapest, and the browser is on its product page. */
export async function expectBuyOn(w: StoreWorld, store: string): Promise<void> {
  const app = required(w.app, 'app')
  const desk = await app.desk()
  expect(desk.controls, show(desk)).toEqual(['Buy'])
  expect(desk.buy, show(desk)).toBe(store)
  expect(desk.ranking[0]?.store, show(desk)).toBe(store)
  const view = await app.browser()
  expect(new URL(view.url ?? 'about:blank').pathname, show(view)).toBe(`/sites/${site(store)}/product/${heldProduct(w).slug}`)
  expect(desk.link).toBe(view.url)
}

/** The browser on a store's checkout: the product in its cart, the address on file and the test Visa filled. */
export async function expectCheckout(w: World, store: string): Promise<void> {
  const view = await required(w.app, 'app').browser()
  const product = heldProduct(w)
  expect(new URL(view.url ?? 'about:blank').pathname, show(view)).toBe(`/sites/${site(store)}/checkout`)
  expect(view.title).toBe(`${store} - Checkout`)
  const lines = (view.text ?? '').split('\n').map((l) => l.trim())
  expect(lines.filter((l) => l === product.name), show(view)).toHaveLength(1)
  expect({
    name: view.fields.ship_name,
    street: view.fields.ship_street,
    city: view.fields.ship_city,
    state: view.fields.ship_state,
    zip: view.fields.ship_zip,
  }).toEqual(SHIP_TO)
  expect(view.fields.card_number?.replace(/\D/g, '')).toBe(CARD_ON_FILE_DIGITS)
  expect(view.fields.card_expiry).toMatch(/^\d{2}\/\d{2}$/)
  expect(view.fields.card_cvc).toMatch(/^\d{3,4}$/)
}

/** Every store's ledger: what its own Place order route recorded. */
export async function storeLedgers(w: World): Promise<Record<string, unknown[]>> {
  const app = required(w.app, 'app')
  return Object.fromEntries(await Promise.all(STORES.map(async (s) => [s, await app.ledger(site(s))] as const)))
}
