"""head-1: in test mode the app's timers run on the virtual clock.

The walk-away outline (D6) moves only the virtual clock, in one jump, and reads the
card and the city's ledger at once. A timer the app schedules in real time (a
call_later, a call_at, an asyncio.sleep in a task) that taps Confirm must fall due
inside that jump, or the outline stays green while the app pays on its own. So
`python -m app --test` runs its event loop on a VirtualTimeLoop, and POST
/test/advance moves the loop's time with the clock and yields until every callback
that fell due has run. These tests apply the reviewer's probe in place: a timer that
confirms must have confirmed by the time the advance answers.
"""

import asyncio
import socket

import httpx
import pytest
import uvicorn
from fixture_sites import Sites

from app.desk import Desk, FakeTexts, VirtualClock
from app.desk.clock import VirtualTimeLoop
from app.web.server import create_app


class Client:
    """The test's HTTP client, on its own thread: a client on the app's loop would see
    its own read timeout fall due inside the advance it is waiting on."""

    def __init__(self, base: str) -> None:
        self._client = httpx.Client(base_url=base)

    async def post(self, path, **kwargs):
        return await asyncio.to_thread(self._client.post, path, **kwargs)

    def close(self) -> None:
        self._client.close()


class StandInHands:
    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def reset(self) -> None:
        pass


class Eye:
    def identify(self, frame):  # pragma: no cover - no frame is pushed here
        raise AssertionError("no frame is pushed in these tests")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run(body):
    """The test server on the loop `python -m app --test` uses."""

    async def main():
        desk = Desk()
        api = create_app(clock=VirtualClock(), desk=desk, hands=StandInHands(), texts=FakeTexts(), sites=Sites(), test_mode=True, eye=Eye())
        port = _free_port()
        server = uvicorn.Server(uvicorn.Config(api, host="127.0.0.1", port=port, log_level="warning"))
        task = asyncio.create_task(server.serve())
        try:
            while not server.started:
                await asyncio.sleep(0.02)
            client = Client(f"http://127.0.0.1:{port}")
            try:
                await body(desk, client)
            finally:
                client.close()
        finally:
            server.should_exit = True
            await task

    with asyncio.Runner(loop_factory=VirtualTimeLoop) as runner:
        runner.run(main())


def _paused(desk):
    ran = []

    async def step():
        desk.require_confirmed()
        ran.append(True)

    desk.pause_for_confirm(step)
    return ran


def _probe_call_later(loop, desk, delay):
    loop.call_later(delay, lambda: loop.create_task(desk.confirm()))


def _probe_call_at(loop, desk, delay):
    loop.call_at(loop.time() + delay, lambda: loop.create_task(Desk.confirm(desk)))


def _probe_sleep(loop, desk, delay):
    async def later():
        await asyncio.sleep(delay)
        await Desk.confirm(desk)

    loop.create_task(later())


PROBES = {"call_later": _probe_call_later, "call_at": _probe_call_at, "asyncio.sleep": _probe_sleep}


@pytest.mark.parametrize("probe", sorted(PROBES))
@pytest.mark.parametrize(("delay", "advance"), [(0.3, 60), (59, 60), (1800, 3600), (2 * 86400, 3 * 86400)])
def test_head_1_a_timer_driven_confirm_falls_due_within_the_advance(probe, delay, advance):
    async def body(desk, client):
        assert (await client.post("/test/reset")).status_code == 200
        ran = _paused(desk)
        PROBES[probe](asyncio.get_running_loop(), desk, delay)
        assert ran == [] and desk.waiting_for_confirm
        r = await client.post("/test/advance", json={"seconds": advance})
        assert r.status_code == 200, r.text
        # The timer fell due inside the jump and its confirm ran before the advance
        # answered: the walk-away outline's next read sees the gate gone, and goes red.
        assert ran == [True] and not desk.waiting_for_confirm

    _run(body)


def test_head_1_a_timer_not_yet_due_stays_pending_after_the_advance():
    async def body(desk, client):
        assert (await client.post("/test/reset")).status_code == 200
        ran = _paused(desk)
        _probe_call_later(asyncio.get_running_loop(), desk, 120)
        assert (await client.post("/test/advance", json={"seconds": 60})).status_code == 200
        assert ran == [] and desk.waiting_for_confirm
        assert (await client.post("/test/advance", json={"seconds": 60})).status_code == 200
        assert ran == [True]

    _run(body)


def test_head_1_the_virtual_loop_never_runs_backwards():
    loop = VirtualTimeLoop()
    try:
        with pytest.raises(ValueError):
            loop.run_until_complete(loop.advance(-1))
    finally:
        loop.close()


def test_head_1_python_m_app_test_serves_on_the_virtual_loop(monkeypatch):
    from app import __main__ as entry

    seen = []

    async def serve(self, sockets=None):
        seen.append(type(asyncio.get_running_loop()))
        self.started = True

    monkeypatch.setattr(uvicorn.Server, "serve", serve)
    assert entry.main(["--test", "--port", str(_free_port())]) == 0
    assert seen == [VirtualTimeLoop]
