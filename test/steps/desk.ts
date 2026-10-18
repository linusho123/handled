// What the identify and ticket bindings share: the world, the fixture images
// and the fields each prints (test/fixtures/images/fields.json, written by
// make-images.py), the user's hands on the webcam, and the far-side reads.
// The far side is the desk's own endpoint (GET /desk, what the page renders),
// the browser as the app's Playwright sees it (GET /test/browser), and the
// fixture site's ledger (GET /test/sites/<site>/ledger), which only the site's
// own pay and contest routes write.
import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { expect } from 'vitest'
import { IMAGES_DIR, getApp, type App, type BrowserView, type Desk, type LedgerEntry } from '../harness/app.ts'

export type World = {
  app?: App
  /** The fixture image of the thing the user holds (or has held) up. */
  thing?: string
  /** The virtual clock when the frame was pushed. */
  heldAt?: string
  /** The eye's latency set for this scenario (seconds of virtual time). */
  eyeDelay?: number
  /** The letter the card showed before Confirm. */
  letter?: string
}

/** D4, D5: the five-second clock. */
export const IDENTIFY_SECONDS = 5
/** The test Visa, the card on file (BUILD-PLAN.md, "Pre-decided"). */
export const CARD_ON_FILE_DIGITS = '4242424242424242'

export type Fixture = { kind: string; fields: Record<string, string | null>; note?: string }
export const FIXTURES: Record<string, Fixture> = JSON.parse(readFileSync(join(IMAGES_DIR, 'fields.json'), 'utf-8'))

export const required = <T>(value: T | undefined, what: string): T => {
  if (value === undefined) throw new Error(`world.${what} read before any step set it`)
  return value
}

/** The worker's app, reset: an empty card, no tab open, every ledger empty. */
export async function openApp(w: World): Promise<App> {
  const app = await getApp()
  await app.reset()
  w.app = app
  const desk = await app.desk()
  expect(desk.identified).toBeNull()
  expect(desk.notice).toBeNull()
  expect((await app.browser()).tabs).toEqual([])
  return app
}

/** The one fixture image whose recorded fields match every given field. */
export function imageWith(kind: string, match: Record<string, string | null>): string {
  const hits = Object.entries(FIXTURES).filter(
    ([, f]) => f.kind === kind && Object.entries(match).every(([k, v]) => (v === null ? f.fields[k] === null : f.fields[k]?.toLowerCase() === v.toLowerCase())),
  )
  if (hits.length !== 1) throw new Error(`expected one ${kind} fixture with ${JSON.stringify(match)}, found ${hits.map(([n]) => n).join(', ') || 'none'}`)
  return hits[0]![0]
}

/** The fixture that draws something the eye must not identify, checked against fields.json. */
export function unreadable(name: string): string {
  const f = FIXTURES[name]
  if (!f || f.kind !== 'unknown') throw new Error(`${name} is not an unknown-kind fixture`)
  return name
}

/** "a Los Angeles parking ticket for citation 4512087733 on plate 8ABC123", "a blank sheet of paper", … */
export function imageOf(thing: string, w: World): string {
  let m: RegExpMatchArray | null
  if (thing === 'that ticket') return required(w.thing, 'thing')
  if ((m = thing.match(/^a Los Angeles parking ticket for citation (\d+) on plate (\w+)$/)))
    return imageWith('ticket', { city: 'Los Angeles', citation: m[1]!, plate: m[2]!, due: '2026-11-02' })
  if ((m = thing.match(/^an LADWP bill for \$([\d.]+) due (\S+) on account (\d+)$/)))
    return imageWith('bill', { biller: 'LADWP', amount: m[1]!, due: m[2]!, account: m[3]! })
  if ((m = thing.match(/^a (\d+ oz) bottle of (.+)$/))) return imageWith('product', { name: m[2]!, size: m[1]! })
  const unknowns: Record<string, string> = {
    "a parking ticket at arm's length so the digits blur": 'ticket-blurred.png',
    'a parking ticket moving so fast the frame is smeared': 'ticket-smeared.png',
    'a blank sheet of paper': 'blank-sheet.png',
    'a coffee mug with no label': 'mug.png',
  }
  if (thing in unknowns) return unreadable(unknowns[thing]!)
  throw new Error(`no fixture image for "${thing}"`)
}

/** The user holds the thing up: its frame reaches the app the way the page's webcam frames do. */
export async function holdUp(w: World, image: string): Promise<void> {
  const app = required(w.app, 'app')
  w.thing = image
  w.heldAt = app.now
  await app.frame(image)
}

/** Seconds of virtual time since the frame. */
export function sinceHeld(w: World): number {
  const app = required(w.app, 'app')
  return (Date.parse(`${app.now}Z`) - Date.parse(`${required(w.heldAt, 'heldAt')}Z`)) / 1000
}

/** Move the clock to `seconds` after the frame (never backwards). */
export async function toSecondsAfterFrame(w: World, seconds: number): Promise<void> {
  const app = required(w.app, 'app')
  const step = Math.round((seconds - sinceHeld(w)) * 1000) / 1000
  if (step < 0) throw new Error(`the clock is already ${sinceHeld(w)} s past the frame`)
  if (step > 0) await app.advance(step)
}

/** Watch the card on the clock, half a second at a time, until it names something; at most five seconds after the frame. */
export async function cardWithinFive(w: World): Promise<Desk> {
  const app = required(w.app, 'app')
  for (;;) {
    const desk = await app.desk()
    if (desk.identified !== null) {
      expect(sinceHeld(w)).toBeLessThanOrEqual(IDENTIFY_SECONDS)
      return desk
    }
    if (sinceHeld(w) >= IDENTIFY_SECONDS) throw new Error(`no card ${IDENTIFY_SECONDS} s after the frame: ${JSON.stringify(desk)}`)
    await toSecondsAfterFrame(w, Math.min(IDENTIFY_SECONDS, sinceHeld(w) + 0.5))
  }
}

export const KINDS: Record<string, string> = { 'a parking ticket': 'ticket', 'a bill': 'bill', 'a product': 'product' }

export function path(view: BrowserView): string {
  if (view.url === null) throw new Error('no tab is open')
  return new URL(view.url).pathname
}

export function query(view: BrowserView, key: string): string | null {
  return view.url === null ? null : new URL(view.url).searchParams.get(key)
}

export const show = (value: unknown) => JSON.stringify(value)

/** The city's records for one citation, as its own routes wrote them. */
export async function cityRecords(w: World, citation: string, kind?: string): Promise<LedgerEntry[]> {
  const ledger = await required(w.app, 'app').ledger('la-citations')
  return ledger.filter((e) => e.citation === citation && (kind === undefined || e.kind === kind))
}
