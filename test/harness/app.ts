// The app under test: `python -m app --test --port <free>`, spawned once per
// test worker (getApp) and driven black-box over HTTP. It is ready when
// POST /test/reset answers. Step bindings reset it before each scenario, push
// fixture images, advance its virtual clock, set fixture-site faults and read
// back the far side: the desk (GET /desk, what the page renders), the browser
// (GET /test/browser, Playwright's own view), the texts fake (GET /test/texts)
// and each fixture site's ledger (GET /test/sites/<site>/ledger).
// Copied from Taken's harness, TAKEN_ renamed HANDLED_.
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { join, resolve } from 'node:path'

export const ROOT = resolve(import.meta.dirname, '..', '..')
export const IMAGES_DIR = join(ROOT, 'test', 'fixtures', 'images')

export const SITES = ['la-citations', 'ladwp', 'target', 'walmart', 'amazon'] as const
export type SiteName = (typeof SITES)[number]

/** The card as GET /desk returns it: what the page renders. */
export type Desk = {
  identified: { kind: string; fields: Record<string, string | null> } | null
  done: string | null
  deadline: string | null
  deadline_note: string | null
  link: string | null
  controls: string[]
  question: string | null
  letter: string | null
  notice: string | null
  failed_step: string | null
  /** A bill that could not be paid online: the phone number printed on it (D15). */
  call_to_pay: string | null
  /** The product chore: the stores listing it, cheapest first, with the price their page shows. */
  ranking: { store: string; price: string; link: string }[]
  /** The stores marked "not found", in store order. */
  not_found: string[]
  /** The store the Buy control is on, while it shows. */
  buy: string | null
}

/** The browser as the app's Playwright sees it. */
export type BrowserView = {
  url: string | null
  title: string | null
  fields: Record<string, string>
  /** The active tab's visible text (absent with no tab open). */
  text?: string
  tabs: { url: string; title: string }[]
}

export type LedgerEntry = Record<string, unknown> & { kind: string }

/** HANDLED_PYTHON, else .venv/bin/python, else python3 (scripts/py.mjs resolves the same way). */
export function python(): string {
  if (process.env.HANDLED_PYTHON) return process.env.HANDLED_PYTHON
  const venv = join(ROOT, '.venv', 'bin', 'python')
  return existsSync(venv) ? venv : 'python3'
}

function freePort(): Promise<number> {
  return new Promise((ok, fail) => {
    const server = createServer()
    server.on('error', fail)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      server.close(() => (typeof address === 'object' && address ? ok(address.port) : fail(new Error('no port'))))
    })
  })
}

export class App {
  readonly url: string
  /** The app's virtual clock as of the last reset or advance (ISO, local time). */
  now = ''
  private readonly child: ChildProcess
  private output = ''

  private constructor(child: ChildProcess, url: string) {
    this.child = child
    this.url = url
    child.stdout?.on('data', (chunk: Buffer) => (this.output += chunk.toString()))
    child.stderr?.on('data', (chunk: Buffer) => (this.output += chunk.toString()))
  }

  static async start(timeoutMs = 30_000): Promise<App> {
    const port = await freePort()
    const child = spawn(python(), ['-m', 'app', '--test', '--port', String(port)], {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    const app = new App(child, `http://127.0.0.1:${port}`)
    const deadline = Date.now() + timeoutMs
    for (;;) {
      if (child.exitCode !== null) throw new Error(`the app exited (${child.exitCode}) before answering /test/reset:\n${app.output}`)
      try {
        await app.reset()
        return app
      } catch (err) {
        if (Date.now() > deadline) {
          app.stop()
          throw new Error(`the app did not answer /test/reset within ${timeoutMs} ms:\n${app.output}`, { cause: err })
        }
        await new Promise((r) => setTimeout(r, 100))
      }
    }
  }

  async request(method: 'GET' | 'POST', path: string, body?: unknown, contentType = 'application/json'): Promise<Response> {
    const init: RequestInit = { method, redirect: 'manual' }
    if (body !== undefined) {
      init.body = body instanceof Uint8Array || body instanceof URLSearchParams ? body : JSON.stringify(body)
      init.headers = { 'Content-Type': body instanceof URLSearchParams ? 'application/x-www-form-urlencoded' : contentType }
    }
    return fetch(this.url + path, init)
  }

  private async json<T>(method: 'GET' | 'POST', path: string, body?: unknown, contentType?: string): Promise<T> {
    const res = await this.request(method, path, body, contentType)
    if (!res.ok) throw new Error(`${method} ${path} answered ${res.status}: ${await res.text()}`)
    return (await res.json()) as T
  }

  /**
   * Clock to its start (or to `start`, a local ISO time such as "2026-10-17T07:50");
   * the desk, the texts, every fixture site's ledger, faults, prices and cart,
   * and every browser tab emptied. Returns the clock's time.
   */
  async reset(start?: string): Promise<string> {
    this.now = (await this.json<{ now: string }>('POST', '/test/reset', start === undefined ? undefined : { start })).now
    return this.now
  }

  /** Push a named fixture image from test/fixtures/images (e.g. "la-ticket.png"). */
  async frame(name: string): Promise<void> {
    await this.json('POST', '/test/frame', new Uint8Array(readFileSync(join(IMAGES_DIR, name))), 'image/png')
  }

  /** Move the virtual clock forward; returns the new time. */
  async advance(seconds: number): Promise<string> {
    this.now = (await this.json<{ now: string }>('POST', '/test/advance', { seconds })).now
    return this.now
  }

  /** Test mode: how long the eye takes to answer, in seconds of virtual time. */
  async eyeDelay(seconds: number): Promise<void> {
    await this.json('POST', '/test/eye', { seconds })
  }

  /** The user taps a control on the card other than Confirm (Pay, Contest, Buy), as the page does. */
  tap(control: string): Promise<Response> {
    return this.request('POST', '/tap', { control })
  }

  /** The user taps Confirm, as the page's Confirm button does. */
  confirm(): Promise<Response> {
    return this.request('POST', '/confirm')
  }

  /** The user says (or types) something, as the page's microphone button does. */
  say(text: string): Promise<Response> {
    return this.request('POST', '/say', { text })
  }

  /** The card, through the page's own endpoint. */
  desk(): Promise<Desk> {
    return this.json('GET', '/desk')
  }

  /** The browser, as the app's Playwright sees it. */
  browser(): Promise<BrowserView> {
    return this.json('GET', '/test/browser')
  }

  /** What the texts fake was asked to send. */
  texts(): Promise<{ to: string; body: string; at: string; key: string | null }[]> {
    return this.json('GET', '/test/texts')
  }

  /** Set a fixture site's fault (null clears it) and, for a store, its prices by product slug. */
  setSite(site: SiteName, settings: { fault?: string | null; prices?: Record<string, string> }): Promise<unknown> {
    return this.json('POST', '/test/sites', { site, ...settings })
  }

  /** What a fixture site's own routes recorded as submitted, paid or ordered. */
  ledger(site: SiteName): Promise<LedgerEntry[]> {
    return this.json('GET', `/test/sites/${site}/ledger`)
  }

  stop(): void {
    this.child.kill()
  }
}

let shared: Promise<App> | undefined

/** The worker's one app, started on first use. */
export function getApp(): Promise<App> {
  shared ??= App.start()
  return shared
}

/** Stop the worker's app, if one was started (afterAll). */
export async function closeApp(): Promise<void> {
  if (!shared) return
  const app = await shared.catch(() => undefined)
  shared = undefined
  app?.stop()
}
