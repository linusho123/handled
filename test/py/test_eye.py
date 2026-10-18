"""The eye replays its cassettes: every fixture image reads as fields.json records it,
a missing cassette fails loudly, and a cassette holds the request hash and the
response body only."""

import json
from pathlib import Path

import pytest

from app.eye import GEMINI_MODEL, Frame, GeminiEye, parse_identification, size_text
from app.eye.cassette import CASSETTES, Cassette, CassetteMissing

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "test" / "fixtures" / "images"
FIELDS = json.loads((IMAGES / "fields.json").read_text())
REASON = "the meter was broken, I put in two dollars and it never started"


def _frame(name):
    return Frame(image=(IMAGES / name).read_bytes(), content_type="image/png")


@pytest.fixture
def eye():
    return GeminiEye(Cassette(record=False))


@pytest.mark.parametrize("name", sorted(FIELDS))
def test_every_fixture_image_reads_as_it_was_drawn(eye, name):
    ident = eye.identify(_frame(name))
    expected = FIELDS[name]
    assert ident.kind == expected["kind"]
    for key, value in expected["fields"].items():
        got = ident.fields.get(key)
        if key == "name":
            assert got.lower() == value.lower()  # the label's typography, not a different name
        else:
            assert got == value, key


def test_a_product_with_its_size_hidden_gets_the_variant_question(eye):
    ident = eye.identify(_frame("cholula-size-hidden.png"))
    assert ident.kind == "product"
    assert ident.fields["size"] is None
    assert ident.variant_question == "Is this the 32 oz?"


def test_the_contest_letter_is_one_paragraph_from_the_spoken_reason(eye):
    ticket = eye.identify(_frame("la-ticket.png")).fields
    letter = eye.write_letter(ticket, REASON)
    assert "\n" not in letter
    assert "meter" in letter.lower() and "broken" in letter.lower() and "two dollars" in letter.lower()


def test_a_missing_cassette_fails_loudly_and_never_calls(tmp_path):
    eye = GeminiEye(Cassette(tmp_path, record=False))

    def no_client():
        raise AssertionError("a replaying eye reached for a live client")

    eye._live_client = no_client
    with pytest.raises(CassetteMissing, match="no cassette"):
        eye.identify(_frame("la-ticket.png"))
    with pytest.raises(CassetteMissing):
        eye.write_letter({"citation": "1", "city": "X", "plate": "Y"}, "a reason")


def test_recording_stores_the_request_hash_and_the_response_only(tmp_path):
    cassette = Cassette(tmp_path, record=True)
    request = {"call": "identify", "model": GEMINI_MODEL, "prompt": "p", "image_sha256": "0" * 64}
    assert cassette.play("identify", request, lambda: '{"kind": "unknown"}') == '{"kind": "unknown"}'
    [path] = list(tmp_path.iterdir())
    stored = json.loads(path.read_text())
    assert set(stored) == {"request_hash", "response"}
    assert cassette.play("identify", request, lambda: pytest.fail("a recorded request was asked again")) == '{"kind": "unknown"}'


def test_every_committed_cassette_is_used_by_a_fixture_and_holds_no_key(eye):
    used = set()
    for name in FIELDS:
        frame = _frame(name)
        used.add(eye.cassette.path("identify", eye.identify_request(frame)).name)
        ident = eye.identify(frame)
        if ident.kind == "product" and ident.fields.get("size") is None:
            used.add(eye.cassette.path("variant", eye.variant_request(frame, ident.fields["name"])).name)
    ticket = eye.identify(_frame("la-ticket.png")).fields
    used.add(eye.cassette.path("letter", eye.letter_request(ticket, REASON)).name)
    committed = {p.name for p in CASSETTES.glob("*.json")}
    assert committed == used
    for path in CASSETTES.glob("*.json"):
        stored = json.loads(path.read_text())
        assert set(stored) == {"request_hash", "response"}
        assert "AIza" not in path.read_text()


@pytest.mark.parametrize(
    "answer",
    [
        '{"kind": "ticket", "legible": false, "fields": {"city": "Los Angeles", "citation": "4512087733", "plate": "8ABC123", "issued": "2026-10-12"}}',
        '{"kind": "ticket", "legible": true, "fields": {"city": "Los Angeles", "citation": "45120?7733", "plate": "8ABC123", "issued": "2026-10-12"}}',
        '{"kind": "bill", "legible": true, "fields": {"biller": "LADWP", "amount": "148.22"}}',
        "not json",
    ],
)
def test_a_half_read_thing_is_unknown(answer):
    assert parse_identification(answer).kind == "unknown"


def test_sizes_read_the_same_however_the_label_prints_them():
    assert size_text("32 FL OZ") == size_text("32fl oz") == size_text("32 oz.") == "32 oz"
    assert size_text("big") is None
