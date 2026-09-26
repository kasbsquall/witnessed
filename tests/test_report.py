"""Tests for witnessed.report.build_report and generate_report."""

from __future__ import annotations

import json
from pathlib import Path

from witnessed.report import build_report, generate_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scan(tmp_path: Path, changed: list[dict]) -> dict:
    """Write .witnessed/scan.json and return the payload dict."""
    counts: dict[str, int] = {"used": 0, "tested": 0, "agent_witnessed": 0, "unwitnessed": 0}
    for rec in changed:
        level = rec.get("level", "unwitnessed")
        if level in counts:
            counts[level] += 1

    payload = {
        "base": "aaaaaaaabbbbbbbbccccccccdddddddd00000001",
        "head": "aaaaaaaabbbbbbbbccccccccdddddddd00000002",
        "changed": changed,
        "counts": counts,
    }
    witnessed_dir = tmp_path / ".witnessed"
    witnessed_dir.mkdir(exist_ok=True)
    (witnessed_dir / "scan.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _make_gate_verdict(tmp_path: Path, qualname: str, accepted: bool) -> None:
    """Write a gate verdict JSON for *qualname*."""
    gate_dir = tmp_path / ".witnessed" / "gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    safe = qualname.replace(".", "_")
    verdict = {
        "target": qualname,
        "witness": f"witnesses/{qualname}.py",
        "accepted": accepted,
        "reason": None if accepted else "body_not_executed",
        "body_lines_executed": [10, 11] if accepted else [],
    }
    (gate_dir / f"{safe}.json").write_text(json.dumps(verdict), encoding="utf-8")


# ---------------------------------------------------------------------------
# Before/after count tests
# ---------------------------------------------------------------------------


def test_before_count_includes_agent_witnessed() -> None:
    """Before count must be unwitnessed + agent_witnessed (gate promotes them)."""
    changed = [
        {"qualname": "pkg.alpha", "file": "pkg/__init__.py", "change": "added",
         "level": "agent_witnessed", "seen_by": []},
        {"qualname": "pkg.beta",  "file": "pkg/__init__.py", "change": "added",
         "level": "unwitnessed",  "seen_by": []},
        {"qualname": "pkg.gamma", "file": "pkg/__init__.py", "change": "modified",
         "level": "tested",       "seen_by": ["tested"]},
    ]
    scan_data = {
        "base": "aaa",
        "head": "bbb",
        "changed": changed,
        "counts": {"used": 0, "tested": 1, "agent_witnessed": 1, "unwitnessed": 1},
    }
    html = build_report(scan_data, {}, "add some functions")

    # Before: 1 unwitnessed + 1 agent_witnessed = 2 of 3
    assert "2 of 3 changed functions were never seen running" in html


def test_after_count_only_unwitnessed() -> None:
    """After count in the subtitle must reflect only 'unwitnessed', not agent_witnessed."""
    changed = [
        {"qualname": "pkg.alpha", "file": "pkg/__init__.py", "change": "added",
         "level": "agent_witnessed", "seen_by": []},
        {"qualname": "pkg.beta",  "file": "pkg/__init__.py", "change": "added",
         "level": "unwitnessed",  "seen_by": []},
    ]
    scan_data = {
        "base": "aaa",
        "head": "bbb",
        "changed": changed,
        "counts": {"used": 0, "tested": 0, "agent_witnessed": 1, "unwitnessed": 1},
    }
    html = build_report(scan_data, {}, "add functions")

    # After: only 1 unwitnessed, not 2
    assert "after gate: 1 of 2 still unwitnessed" in html


def test_all_witnessed_before_after() -> None:
    """When 0 are unwitnessed after, both counts show correctly."""
    changed = [
        {"qualname": "pkg.alpha", "file": "pkg/__init__.py", "change": "added",
         "level": "agent_witnessed", "seen_by": []},
        {"qualname": "pkg.beta",  "file": "pkg/__init__.py", "change": "added",
         "level": "agent_witnessed", "seen_by": []},
    ]
    scan_data = {
        "base": "aaa",
        "head": "bbb",
        "changed": changed,
        "counts": {"used": 0, "tested": 0, "agent_witnessed": 2, "unwitnessed": 0},
    }
    html = build_report(scan_data, {}, "add two functions")

    # Before: 2 (both were unwitnessed before gate)
    assert "2 of 2 changed functions were never seen running" in html
    # After: 0 still unwitnessed
    assert "after gate: 0 of 2 still unwitnessed" in html


# ---------------------------------------------------------------------------
# Gate verdict in cell detail
# ---------------------------------------------------------------------------


def test_agent_witnessed_cell_shows_witness_file() -> None:
    """An agent_witnessed cell must show the witness file and gate verdict."""
    changed = [
        {"qualname": "pkg.foo", "file": "pkg/__init__.py", "change": "added",
         "level": "agent_witnessed", "seen_by": []},
    ]
    scan_data = {
        "base": "aaa", "head": "bbb", "changed": changed,
        "counts": {"used": 0, "tested": 0, "agent_witnessed": 1, "unwitnessed": 0},
    }
    gate_verdicts = {
        "pkg.foo": {
            "target": "pkg.foo",
            "witness": "witnesses/pkg.foo.py",
            "accepted": True,
            "reason": None,
            "body_lines_executed": [5],
        }
    }
    # Names carry <wbr> break points in the markup; the visible text is unchanged.
    html = build_report(scan_data, gate_verdicts, "").replace("<wbr>", "")

    assert "witnesses/pkg.foo.py" in html
    assert "accepted" in html


# ---------------------------------------------------------------------------
# generate_report integration: writes docs/report.html
# ---------------------------------------------------------------------------


def test_generate_report_writes_file(tmp_path: Path) -> None:
    """generate_report must write docs/report.html containing the counts."""
    changed = [
        {"qualname": "mypkg.do_it", "file": "mypkg/__init__.py", "change": "added",
         "level": "unwitnessed", "seen_by": []},
        {"qualname": "mypkg.helper", "file": "mypkg/__init__.py", "change": "modified",
         "level": "tested", "seen_by": ["tested"]},
    ]
    _make_scan(tmp_path, changed)
    # No gate verdicts for this test.

    # generate_report calls git; monkeypatch by making head SHA invalid so it
    # falls back to empty commit message gracefully.
    out = generate_report(tmp_path)

    assert out.exists()
    assert out.name == "report.html"
    html = out.read_text(encoding="utf-8")

    # 1 agent_witnessed=0 + unwitnessed=1 = 1 before; total=2
    assert "1 of 2 changed functions were never seen running" in html
    # after: 1 unwitnessed
    assert "after gate: 1 of 2 still unwitnessed" in html
    # Function names appear
    assert "do_it" in html
    assert "helper" in html
