"""Live mode's wiring (python -m app without --test), checked without running it: the
real clock, live Gemini with no cassette, a headed Chromium on the real sites, the texts
sender from the environment, and no /test/* endpoint. Live mode itself is exercised by
hand at the demo integration (PD); no test reaches Gemini, Photon, Twilio or a real site."""

import json

import pytest
from fastapi.testclient import TestClient

import app.__main__ as main_module
from app.desk import Desk, FakeTexts, RealClock, VirtualClock
from app.desk.texts import ChainTexts
from app.eye import Frame
from app.eye.cassette import Cassette
from app.eye import GeminiEye
from app.web.server import create_app

LIVE_KEYS = ("GEMINI_API_KEY", "PHOTON_API_KEY", "PHOTON_PROJECT_ID", "PHOTON_AGENT_HANDLE", "TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_FROM", "TWILIO_TO", "HANDLED_SITES", "HANDLED_RECORD")


def _client(api):
    """A client that does not run the app's lifespan, so no browser is launched."""
    return TestClient(api)


@pytest.fixture
def launched(monkeypatch):
    for key in LIVE_KEYS:
        monkeypatch.delenv(key, raising=False)
    seen = {}

    def create(**kwargs):
        seen.update(kwargs)
        return create_app(**kwargs)

    monkeypatch.setattr("app.web.server.create_app", create)
    monkeypatch.setattr("uvicorn.run", lambda api, **kw: seen.update(api=api, run=kw))
    return seen


def test_live_mode_runs_the_real_clock_live_gemini_headed_chromium_and_the_real_sites(launched, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    assert main_module.main(["--port", "8123"]) == 0
    assert isinstance(launched["clock"], RealClock)
    assert launched["test_mode"] is False and launched["sites"] is None
    assert launched["hands"].headless is False and launched["hands"].loopback_only is False
    assert isinstance(launched["eye"], GeminiEye) and launched["eye"].cassette.live is True
    assert isinstance(launched["texts"], ChainTexts) and launched["texts"].senders == []
    portal = launched["sitemap"].city("Los Angeles")
    assert portal.lookup_url.startswith("https://") and "127.0.0.1" not in portal.lookup_url
    client = _client(launched["api"])
    assert client.get("/desk").status_code == 200
    assert client.post("/test/reset").status_code == 404 and client.get("/test/texts").status_code == 404
    assert client.get("/sites/la-citations/").status_code == 404
    assert "loop" not in launched["run"]  # the real event loop, not the virtual one


def test_live_mode_on_the_fixture_sites_serves_them_but_no_test_endpoint(launched, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("HANDLED_SITES", "fixtures")
    assert main_module.main(["--port", "8124"]) == 0
    assert launched["hands"].headless is False and launched["hands"].loopback_only is True
    assert launched["sitemap"].city("Los Angeles").lookup_url == "http://127.0.0.1:8124/sites/la-citations/"
    client = _client(launched["api"])
    assert client.get("/sites/la-citations/").status_code == 200
    assert client.post("/test/reset").status_code == 404 and client.get("/test/sites/la-citations/ledger").status_code == 404


def test_live_mode_picks_photon_when_its_keys_are_present(launched, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "not-a-real-key")
    monkeypatch.setenv("PHOTON_API_KEY", "pho_sk_x")
    monkeypatch.setenv("PHOTON_PROJECT_ID", "pho_prj_x")
    monkeypatch.setattr("app.desk.texts.PhotonTexts.prepare", lambda self: None)  # no handshake call from a test
    assert main_module.main([]) == 0
    assert [s.name for s in launched["texts"].senders] == ["photon"]


@pytest.mark.parametrize(
    "argv, env",
    [([], {}), ([], {"GEMINI_API_KEY": "x", "HANDLED_SITES": "staging"}), (["--test"], {"HANDLED_SITES": "real"})],
)
def test_live_mode_refuses_to_start_without_what_it_needs(launched, monkeypatch, argv, env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    assert main_module.main(argv) == 2
    assert "run" not in launched


def test_a_live_cassette_asks_the_model_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("HANDLED_RECORD", "1")
    cassette = Cassette(directory=tmp_path, live=True)
    assert cassette.record is False
    assert cassette.play("identify", {"call": "identify", "image_sha256": "abc"}, lambda: json.dumps({"kind": "unknown"})) == '{"kind": "unknown"}'
    assert list(tmp_path.iterdir()) == []
    eye = GeminiEye(cassette)
    eye._generate = lambda parts, json_answer: json.dumps({"kind": "unknown", "legible": False, "fields": {}})
    assert eye.identify(Frame(image=b"never-recorded", content_type="image/jpeg")).kind == "unknown"


class _StandInHands:
    async def start(self):
        pass

    async def stop(self):
        pass


class _Clock(VirtualClock):
    """Stands in for the real clock: it moves when the test moves it."""


def test_live_each_request_reads_the_clock_so_a_due_day_before_text_goes():
    from datetime import datetime

    from app.eye import Identification

    clock, texts = _Clock(datetime(2026, 11, 1, 8, 59, 0)), FakeTexts()
    desk = Desk()
    api = create_app(clock=clock, desk=desk, hands=_StandInHands(), texts=texts, test_mode=False)
    desk.identification = Identification(kind="ticket", fields={"citation": "4512087733"}, confidence=1.0)
    desk.card.deadline = "2026-11-02"
    desk.report("Ready to pay citation 4512087733, waiting for you")
    with TestClient(api) as client:
        client.get("/desk")
        assert len(texts.sent) == 1
        clock.advance(60)
        client.get("/desk")
    assert [t["at"] for t in texts.sent] == ["2026-11-01T08:59:00", "2026-11-01T09:00:00"]
    assert "citation 4512087733" in texts.sent[1]["body"]
