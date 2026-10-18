"""head-1: P0 installs no Browser Use. The operator's ruling (2026-10-18, commit 7c85d0e):
Browser Use is not installed before P4, and P4 adds `browser-use` to the Python
dependencies (BUILD-PLAN.md, P4). `npm run setup:py` installs every dependency in
pyproject.toml, so until P4 neither Browser Use nor the settings package it pulled in
may be listed there. P4 removes this test with the ruling it carries out."""

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
