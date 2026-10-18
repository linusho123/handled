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
