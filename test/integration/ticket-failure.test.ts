import { afterAll, beforeAll, describe, expect, test } from 'vitest'
import { App } from '../harness/app.ts'

// risk-1: a step after the lookup that fails (the city's page stops answering
// once Pay or Contest is tapped) stops the chore where it stands, as the
// architecture says: the card names the step, no control is left to tap, the
// browser stays on the page it reached, nothing is submitted, and nobody waits
// out a 30 s Playwright timeout for it. Before the fix the tap answered a 500
// after 30 s and the card held controls [] with failed_step null.
const BOUND_MS = 10_000

describe('a ticket step that fails after the lookup', () => {
  let app: App
  beforeAll(async () => {
    app = await App.start()
  })
  afterAll(() => app?.stop())

  async function lookedUp(): Promise<void> {
    await app.reset()
    await app.frame('la-ticket.png')
    expect((await app.desk()).controls).toEqual(['Pay', 'Contest'])
    await app.setSite('la-citations', { fault: 'down' })
  }

  test.each([
    ['Pay', '/sites/la-citations/pay', "Could not reach the city's payment page"],
    ['Contest', '/sites/la-citations/contest', "Could not reach the city's contest form"],
  ])('tapping %s names the step, keeps the blank tab and submits nothing', async (control, path, step) => {
    await lookedUp()
    const started = Date.now()
    const res = await app.tap(control)
    expect(Date.now() - started).toBeLessThan(BOUND_MS)
    expect(res.status, await res.clone().text()).toBe(200)
    const desk = await app.desk()
    expect(desk.failed_step, JSON.stringify(desk)).toBe(step)
    expect(desk.controls).toEqual([])
    expect(desk.done).toBeNull()
    const view = await app.browser()
    expect(view.tabs, JSON.stringify(view)).toHaveLength(1)
    expect(new URL(view.url!).pathname).toBe(path)
    expect(view.title).toBe('')
    expect(view.fields).toEqual({})
    expect(desk.link).toBe(view.url)
    expect(await app.ledger('la-citations')).toEqual([])
    // The chore has stopped: Confirm has nothing to let through.
    expect((await app.confirm()).status).toBe(409)
    expect(await app.ledger('la-citations')).toEqual([])
  })
})
