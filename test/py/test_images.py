"""The committed fixture images are exactly what make-images.py draws, with the fields it records."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "test" / "fixtures" / "images"


def _make_images():
    spec = importlib.util.spec_from_file_location("make_images", ROOT / "test" / "fixtures" / "make-images.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_committed_images_are_what_the_script_draws(tmp_path):
    make = _make_images()
    assert make.main([str(tmp_path)]) == 0
    names = sorted(p.name for p in IMAGES.iterdir())
    assert names == sorted(p.name for p in tmp_path.iterdir())
    for name in names:
        assert (IMAGES / name).read_bytes() == (tmp_path / name).read_bytes(), name


def test_the_fields_match_the_scenarios():
    fields = json.loads((IMAGES / "fields.json").read_text())
    assert fields["la-ticket.png"]["fields"] | {} == {
        "city": "Los Angeles", "citation": "4512087733", "plate": "8ABC123", "issued": "2026-10-12",
        "due": "2026-11-02", "amount": "73.00", "violation": "Meter expired",
    }
    assert fields["ladwp-bill.png"]["fields"] == {
        "biller": "LADWP", "account": "1234567890", "amount": "148.22", "due": "2026-11-05", "phone": "1-800-342-5397",
    }
    assert fields["cholula-32oz.png"]["fields"] == {"name": "Cholula Original hot sauce", "size": "32 oz"}
    for name in ("ticket-blurred.png", "blank-sheet.png", "mug.png"):
        assert fields[name]["kind"] == "unknown" and fields[name]["fields"] == {}


def test_the_p1_fixtures_match_their_scenarios():
    fields = json.loads((IMAGES / "fields.json").read_text())
    assert fields["ticket-smeared.png"]["kind"] == "unknown" and fields["ticket-smeared.png"]["fields"] == {}
    assert fields["cholula-size-hidden.png"]["fields"] == {"name": "Cholula Original hot sauce", "size": None}
    for issued in ("2026-10-12", "2026-10-31", "2026-12-20", "2028-02-10"):
        f = fields[f"la-ticket-4512087734-{issued}.png"]["fields"]
        assert (f["citation"], f["plate"], f["issued"], f["due"], f["amount"]) == ("4512087734", "8ABC123", issued, None, "73.00")


def test_the_p2_fixture_matches_its_scenario():
    # report.feature D20: ticket 4512087735, due 2026-10-19, so its day-before text falls on 2026-10-18.
    fields = json.loads((IMAGES / "fields.json").read_text())
    f = fields["la-ticket-4512087735.png"]["fields"]
    assert (f["city"], f["citation"], f["plate"], f["due"], f["amount"]) == ("Los Angeles", "4512087735", "8ABC123", "2026-10-19", "73.00")
