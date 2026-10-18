"""head-1: P0 installs no Browser Use. The operator's ruling (2026-10-18, commit 7c85d0e):
Browser Use is not installed before P4, and P4 adds `browser-use` to the Python
dependencies (BUILD-PLAN.md, P4) only if its cassette can be recorded within thirty
minutes. P4 could not record it (the Gemini key's daily free-tier quota was spent), so
per the ruling Browser Use is left out, the unknown-biller path is "call to pay", and
neither Browser Use nor the settings package it pulls in may be listed in pyproject.toml.
`npm run setup:py` installs every dependency listed there. Whoever adds the finder later
removes this test with the ruling that admits it."""

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def _names(specs: list[str]) -> set[str]:
    names = set()
    for spec in specs:
        name = spec.split(";")[0]
        for stop in "<>=!~[ ":
            name = name.split(stop)[0]
        names.add(name.strip().lower().replace("_", "-"))
    return names


def test_head_1_browser_use_is_not_installed_before_p4():
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    listed = _names(project["dependencies"])
    for extra in project.get("optional-dependencies", {}).values():
        listed |= _names(extra)
    assert "browser-use" not in listed
    assert "pydantic-settings" not in listed
