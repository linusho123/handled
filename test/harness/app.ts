// The app under test: `python -m record --test --port <free> --data <tmp>`,
// spawned once per test worker (getApp) and driven black-box over HTTP. It is
// ready when POST /test/reset answers. Step bindings reset it before each
// scenario, push fixture frames, advance its virtual clock and read back what
// the box, the texts fake, the page and the log file hold.
import { spawn, type ChildProcess } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { createServer } from 'node:net'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

export const ROOT = resolve(import.meta.dirname, '..', '..')
export const FRAMES_DIR = join(ROOT, 'test', 'fixtures', 'frames')

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
  readonly dataDir: string
  readonly logFile: string
  readonly scheduleFile: string
  /** The app's virtual clock as of the last reset or advance (ISO, house time). */
  now = ''
  private readonly child: ChildProcess
  private output = ''

  private constructor(child: ChildProcess, url: string, dataDir: string) {
    this.child = child
    this.url = url
    this.dataDir = dataDir
    this.logFile = join(dataDir, 'log.jsonl')
    this.scheduleFile = join(dataDir, 'schedule.json')
    child.stdout?.on('data', (chunk: Buffer) => (this.output += chunk.toString()))
    child.stderr?.on('data', (chunk: Buffer) => (this.output += chunk.toString()))
  }

  static async start(timeoutMs = 15_000): Promise<App> {
    const port = await freePort()
    const dataDir = mkdtempSync(join(tmpdir(), 'taken-app-'))
    const child = spawn(python(), ['-m', 'record', '--test', '--port', String(port), '--data', dataDir], {
      cwd: ROOT,
      stdio: ['ignore', 'pipe', 'pipe'],
    })
    const app = new App(child, `http://127.0.0.1:${port}`, dataDir)
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
    const init: RequestInit = { method }
    if (body !== undefined) {
      init.body = body instanceof Uint8Array ? body : JSON.stringify(body)
      init.headers = { 'Content-Type': contentType }
    }
    return fetch(this.url + path, init)
  }

  private async json<T>(method: 'GET' | 'POST', path: string, body?: unknown, contentType?: string): Promise<T> {
    const res = await this.request(method, path, body, contentType)
    if (!res.ok) throw new Error(`${method} ${path} answered ${res.status}: ${await res.text()}`)
    return (await res.json()) as T
  }

  /**
   * Clock to its start (or to `start`, an ISO house time such as "2026-10-17T07:50");
   * frames, the eye's reference, texts, the voice queue, the schedule and the log
   * emptied. Returns the clock's time.
   */
  async reset(start?: string): Promise<string> {
    this.now = (await this.json<{ now: string }>('POST', '/test/reset', start === undefined ? undefined : { start })).now
    return this.now
  }

  /** Push a named fixture frame from test/fixtures/frames (e.g. "tray-b123-h2.png"). */
  async frame(name: string): Promise<void> {
    await this.json('POST', '/test/frame', new Uint8Array(readFileSync(join(FRAMES_DIR, name))), 'image/png')
  }

  /** Move the virtual clock forward; returns the new time. */
  async advance(seconds: number): Promise<string> {
    this.now = (await this.json<{ now: string }>('POST', '/test/advance', { seconds })).now
    return this.now
  }

  /** What the box is told to say, read through the box's own poll endpoint (which drains it). */
  async boxNext(): Promise<{ id: number; text: string }[]> {
    return this.json('GET', '/box/next')
  }

  /** The caretaker's page, as served. */
  async page(): Promise<string> {
    const res = await this.request('GET', '/')
    if (!res.ok) throw new Error(`GET / answered ${res.status}: ${await res.text()}`)
    return res.text()
  }

  /** Write the schedule file the app reads (the written configuration; setup by voice is P5). */
  writeSchedule(schedule: unknown): void {
    writeFileSync(this.scheduleFile, JSON.stringify(schedule, null, 2))
  }

  /** What the texts fake was asked to send. */
  texts(): Promise<{ to: string; body: string }[]> {
    return this.json('GET', '/test/texts')
  }

  /** The log file, read directly: one parsed entry per line. */
  logEntries(): Record<string, unknown>[] {
    if (!existsSync(this.logFile)) return []
    return readFileSync(this.logFile, 'utf8')
      .split('\n')
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line) as Record<string, unknown>)
  }

  stop(): void {
    this.child.kill()
    rmSync(this.dataDir, { recursive: true, force: true })
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
