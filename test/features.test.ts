import { copyFileSync, mkdtempSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, join, resolve } from 'node:path'
import { afterAll } from 'vitest'
import { runFeatures, type Definer, type WipEntry } from 'gherkin-node-test/vitest'
import { closeApp } from './harness/app.ts'
import bill from './steps/bill.steps.ts'
import identify from './steps/identify.steps.ts'
import product from './steps/product.steps.ts'
import report from './steps/report.steps.ts'
import ticket from './steps/ticket.steps.ts'

// gherkin-node-test over features/. One definer per feature file joins here as
// its phase binds it (test/steps/<feature>.steps.ts), driving the worker's one
// app (test/harness/app.ts), stopped after the run.
//
// FEATURES (fast lane only) names the feature files to run, by basename or
// path, separated by commas or spaces; unset runs them all. The full lane
// unsets it. HANDLED_MANIFEST=1 (npm run manifest) writes run-manifest.ndjson,
// and only on an unfiltered run, because a partial account is not an account.

const ROOT = resolve(import.meta.dirname, '..')
const FEATURE_DIR = join(ROOT, 'features')

// The wip register: features (or scenarios) not yet bound. It only shrinks.
// P1 bound ticket and identify; P2 bound report; P3 bound product, the two D8
// scenarios' store steps and report's Cholula row; P4 bound bill and report's
// LADWP row (the bill paused at Confirm on its payment page). Nothing is held.
const WIP: WipEntry[] = []

// eslint-disable-next-line @typescript-eslint/no-explicit-any -- each feature's world type is its own
const definers: Record<string, Definer<any>> = {
  bill,
  identify,
  product,
  report,
  ticket,
}

const all = readdirSync(FEATURE_DIR).filter((f) => f.endsWith('.feature')).map((f) => basename(f, '.feature'))
const requested = (process.env.FEATURES ?? '')
  .split(/[\s,]+/)
  .filter(Boolean)
  .map((f) => basename(f, '.feature'))
for (const name of requested) {
  if (!all.includes(name)) throw new Error(`FEATURES names ${name}, which is not a feature file in features/`)
}

const filtered = requested.length > 0
if (process.env.HANDLED_MANIFEST === '1' && filtered) {
  throw new Error('HANDLED_MANIFEST=1 with FEATURES set: the manifest is written only by a run over every feature file')
}

const selected = filtered ? requested : all
let dir = FEATURE_DIR
if (filtered) {
  dir = mkdtempSync(join(tmpdir(), 'handled-features-'))
  for (const name of selected) copyFileSync(join(FEATURE_DIR, `${name}.feature`), join(dir, `${name}.feature`))
}

const featureOf = (entry: WipEntry) => (typeof entry === 'string' ? entry : entry.feature)
const pick = <T>(entries: Record<string, T>) =>
  Object.fromEntries(Object.entries(entries).filter(([name]) => selected.includes(name)))

afterAll(closeApp)

const manifest = join(ROOT, 'run-manifest.ndjson')
runFeatures(dir, pick(definers), {
  wip: WIP.filter((entry) => selected.includes(featureOf(entry))),
  ...(process.env.HANDLED_MANIFEST === '1' ? { manifest } : {}),
})
