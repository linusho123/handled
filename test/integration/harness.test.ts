import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { afterAll, beforeAll, describe, expect, test } from 'vitest'
import { App, IMAGES_DIR, SITES } from '../harness/app.ts'

// The harness smoke test (P0's gate): the app spawns in test mode, answers
// /test/reset, and every /test/* endpoint reports what the app holds, nothing
// pre-seeded. Each fixture site's ledger is written only by a real form post
// to its own submit, pay or order route.
describe('the app in test mode', () => {
  let app: App
  beforeAll(async () => {
    app = await App.start()
  })
  afterAll(() => app?.stop())

  test('answers /test/reset with the virtual clock at its start', async () => {
    expect(await app.reset()).toBe('2026-10-17T00:00:00')
  })

  test('holds an empty card, no texts, no tabs and empty ledgers after a reset', async () => {
    await app.reset()
    expect(await app.desk()).toEqual({
      identified: null,
      done: null,
      deadline: null,
      deadline_note: null,
      link: null,
      controls: [],
      question: null,
      letter: null,
      notice: null,
      failed_step: null,
      call_to_pay: null,
      ranking: [],
      not_found: [],
      buy: null,
    })
    expect(await app.texts()).toEqual([])
    expect(await app.browser()).toEqual({ url: null, title: null, fields: {}, tabs: [] })
    for (const site of SITES) expect(await app.ledger(site)).toEqual([])
    expect((await app.request('GET', '/test/sites/nowhere/ledger')).status).toBe(404)
  })

  test('advances its clock only when told, and reset puts it back', async () => {
    await app.reset()
    expect(await app.advance(9 * 3600 + 5)).toBe('2026-10-17T09:00:05')
    expect(await app.advance(0)).toBe('2026-10-17T09:00:05')
    expect(await app.advance(4.9)).toBe('2026-10-17T09:00:09.900000')
    expect(await app.reset()).toBe('2026-10-17T00:00:00')
    expect((await app.request('POST', '/test/advance', { seconds: -5 })).status).toBe(400)
    expect((await app.request('POST', '/test/advance', { seconds: '5' })).status).toBe(400)
  })

  test('resets to an optional start and refuses a start that is not a time', async () => {
    expect(await app.reset('2026-10-31T08:59')).toBe('2026-10-31T08:59:00')
    expect(await app.reset()).toBe('2026-10-17T00:00:00')
    expect((await app.request('POST', '/test/reset', { start: 'tomorrow' })).status).toBe(400)
  })

  test('accepts the fixture images and refuses what is not an image; an unreadable frame identifies nothing', async () => {
    await app.reset()
    const names = readdirSync(IMAGES_DIR).filter((f) => f.endsWith('.png')).sort()
    expect(names).toEqual([
      'blank-sheet.png',
      'cholula-32oz.png',
      'cholula-size-hidden.png',
      'la-ticket-4512087734-2026-10-12.png',
      'la-ticket-4512087734-2026-10-31.png',
      'la-ticket-4512087734-2026-12-20.png',
      'la-ticket-4512087734-2028-02-10.png',
      'la-ticket-4512087735.png',
      'la-ticket.png',
      'ladwp-bill.png',
      'mug.png',
      'ticket-blurred.png',
      'ticket-smeared.png',
    ])
    expect((await app.request('POST', '/test/frame', new Uint8Array([1, 2, 3]), 'image/png')).status).toBe(400)
    expect((await app.request('POST', '/frame', new Uint8Array([1, 2, 3]), 'image/jpeg')).status).toBe(400)
    // A frame with no cassette fails loudly; it is never answered with an invented identification.
    const fresh = new Uint8Array(readFileSync(join(IMAGES_DIR, 'mug.png')))
    fresh[fresh.length - 1] = fresh[fresh.length - 1]! ^ 0xff
    const missing = await app.request('POST', '/test/frame', fresh, 'image/png')
    expect([missing.status, await missing.text()]).toEqual([500, expect.stringContaining('no cassette')])
    await app.reset()
    await app.frame('mug.png')
    expect((await app.desk()).identified).toBeNull()
    expect(await app.browser()).toEqual({ url: null, title: null, fields: {}, tabs: [] })
  })

  test('serves the page, and nothing waits for Confirm before a chore exists', async () => {
    await app.reset()
    const page = await app.request('GET', '/')
    expect(page.status).toBe(200)
    expect(page.headers.get('content-type')).toMatch(/^text\/html/)
    expect(await page.text()).toContain('id="card"')
    expect((await app.confirm()).status).toBe(409)
    expect((await app.say('yes')).status).toBe(409)
    expect((await app.tap('Pay')).status).toBe(409)
    expect((await app.tap('Confirm')).status).toBe(400)
    expect((await app.request('POST', '/test/eye', { seconds: -1 })).status).toBe(400)
  })

  test('sets each site fault it knows and refuses any other', async () => {
    await app.reset()
    for (const [site, faults] of [
      ['la-citations', ['down', 'notfound', 'login']],
      ['ladwp', ['down', 'nopage', 'login']],
      ['target', ['nolisting']],
      ['walmart', ['nolisting']],
      ['amazon', ['nolisting']],
    ] as const) {
      for (const fault of faults) expect(await app.setSite(site, { fault })).toMatchObject({ site, fault })
      expect(await app.setSite(site, { fault: null })).toMatchObject({ site, fault: null })
      expect((await app.request('POST', '/test/sites', { site, fault: 'meteor' })).status).toBe(400)
    }
    expect((await app.request('POST', '/test/sites', { site: 'nowhere', fault: 'down' })).status).toBe(400)
    expect((await app.request('POST', '/test/sites', { site: 'ladwp', prices: { 'cholula-original-32oz': '1.00' } })).status).toBe(400)
  })

  test('the city site gives each fault its own answer', async () => {
    await app.reset()
    const lookup = '/sites/la-citations/lookup?citation=4512087733&plate=8ABC123'
    expect((await app.request('GET', lookup)).status).toBe(200)
    await app.setSite('la-citations', { fault: 'down' })
    const down = await app.request('GET', lookup)
    expect([down.status, await down.text()]).toEqual([503, ''])
    await app.setSite('la-citations', { fault: 'notfound' })
    const notFound = await app.request('GET', lookup)
    expect(notFound.status).toBe(404)
    expect(await notFound.text()).toContain('Citation 4512087733 was not found')
    await app.setSite('la-citations', { fault: 'login' })
    const login = await app.request('GET', lookup)
    expect([login.status, login.headers.get('location')]).toEqual([303, '/sites/la-citations/login'])
    await app.reset()
    expect((await app.request('GET', lookup)).status).toBe(200)
  })

  test('visiting every page of every site writes no ledger', async () => {
    await app.reset()
    await app.setSite('walmart', { prices: { 'cholula-original-32oz': '8.98' } })
    for (const path of [
      '/sites/la-citations/',
      '/sites/la-citations/lookup?citation=4512087733&plate=8ABC123',
      '/sites/la-citations/pay?citation=4512087733',
      '/sites/la-citations/contest?citation=4512087733',
      '/sites/ladwp/',
      '/sites/ladwp/pay',
      '/sites/ladwp/search?q=pay+LADWP+bill',
      '/sites/walmart/search?q=cholula+original+32+oz',
      '/sites/walmart/product/cholula-original-32oz',
      '/sites/walmart/cart',
      '/sites/walmart/checkout',
    ]) {
      expect((await app.request('GET', path)).status, path).toBe(200)
    }
    for (const site of SITES) expect(await app.ledger(site)).toEqual([])
  })

  test('a form post to a site’s own pay, contest or order route is what its ledger records, and a reset empties it', async () => {
    await app.reset()
    const card = { card_number: '4242 4242 4242 4242', card_expiry: '12/30', card_cvc: '123' }
    const pay = await app.request('POST', '/sites/la-citations/pay', new URLSearchParams({ citation: '4512087733', ...card }))
    expect(pay.status).toBe(200)
    const contest = await app.request('POST', '/sites/la-citations/contest', new URLSearchParams({ citation: '4512087733', letter: 'The meter was broken.' }))
    expect(contest.status).toBe(200)
    expect(await app.ledger('la-citations')).toEqual([
      { kind: 'payment', citation: '4512087733', amount: '73.00', card_last4: '4242', card_name: '' },
      { kind: 'contest', citation: '4512087733', letter: 'The meter was broken.' },
    ])

    const bill = await app.request('POST', '/sites/ladwp/pay', new URLSearchParams({ account: '1234567890', amount: '$148.22', ...card }))
    expect(bill.status).toBe(200)
    expect(await app.ledger('ladwp')).toEqual([{ kind: 'payment', account: '1234567890', amount: '148.22', card_last4: '4242', card_name: '' }])

    await app.setSite('walmart', { prices: { 'cholula-original-32oz': '8.98' } })
    expect((await app.request('POST', '/sites/walmart/cart', new URLSearchParams({ slug: 'cholula-original-32oz' }))).status).toBe(303)
    expect(await app.ledger('walmart')).toEqual([])
    const ship = { ship_name: 'Pat User', ship_street: '1 Main St', ship_city: 'Los Angeles', ship_state: 'CA', ship_zip: '90001' }
    const order = await app.request('POST', '/sites/walmart/order', new URLSearchParams({ ...ship, ...card }))
    expect(order.status).toBe(200)
    expect(await app.ledger('walmart')).toEqual([
      {
        kind: 'order',
        items: [{ slug: 'cholula-original-32oz', name: 'Cholula Original Hot Sauce, 32 oz', price: '8.98' }],
        total: '8.98',
        ship_to: { name: 'Pat User', street: '1 Main St', city: 'Los Angeles', state: 'CA', zip: '90001' },
        card_last4: '4242',
      },
    ])
    for (const site of ['target', 'amazon'] as const) expect(await app.ledger(site)).toEqual([])

    await app.reset()
    for (const site of SITES) expect(await app.ledger(site)).toEqual([])
  })

  test('a JSON post or an incomplete form is not a form post and records nothing', async () => {
    await app.reset()
    const json = await app.request('POST', '/sites/la-citations/pay', { citation: '4512087733', card_number: '4242424242424242', card_expiry: '12/30', card_cvc: '1' })
    expect(json.status).toBe(422)
    const blank = await app.request('POST', '/sites/la-citations/pay', new URLSearchParams({ citation: '4512087733', card_number: '', card_expiry: '', card_cvc: '' }))
    expect(blank.status).toBe(422) // FastAPI refuses an empty required form field before the route runs
    await app.setSite('la-citations', { fault: 'login' })
    const walled = await app.request('POST', '/sites/la-citations/pay', new URLSearchParams({ citation: '4512087733', card_number: '4242424242424242', card_expiry: '12/30', card_cvc: '123' }))
    expect(walled.status).toBe(303)
    expect(await app.ledger('la-citations')).toEqual([])
  })

  test('a store lists nothing until a price is set, and nothing under nolisting', async () => {
    await app.reset()
    const search = '/sites/target/search?q=cholula+original+32+oz'
    expect(await (await app.request('GET', search)).text()).toContain('No results')
    expect((await app.request('GET', '/sites/target/product/cholula-original-32oz')).status).toBe(404)
    await app.setSite('target', { prices: { 'cholula-original-32oz': '9.49' } })
    expect(await (await app.request('GET', '/sites/target/product/cholula-original-32oz')).text()).toContain("data-price='9.49'")
    await app.setSite('target', { fault: 'nolisting' })
    expect(await (await app.request('GET', search)).text()).toContain('No results')
  })
})
