"""Tests for witnessed.observe — baseline execution and level assignment."""

from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path

import pytest

from witnessed.observe import BaselineCfg, load_baselines, run_baselines, write_baseline_json

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_PKG_SRC = Path(__file__).parent / "fixture_pkg"


def _setup_fixture_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Copy the fixture package into tmp_path so it is under a fake repo root.

    Returns (repo_root, pkg_dir) where:
      - repo_root == tmp_path
      - pkg_dir   == tmp_path / "fixture_pkg" / "mypkg"
    """
    dest = tmp_path / "fixture_pkg"
    shutil.copytree(FIXTURE_PKG_SRC, dest)
    return tmp_path, dest / "mypkg"


# ---------------------------------------------------------------------------
# load_baselines
# ---------------------------------------------------------------------------


def test_load_baselines_commands(tmp_path: Path) -> None:
    """load_baselines must support the 'commands' key (list of lists)."""
    toml_text = textwrap.dedent("""\
        [[baselines]]
        id = "b1"
        kind = "tested"
        commands = [["-m", "pytest", "test/"], ["-m", "pytest", "extra/"]]
    """)
    (tmp_path / "witnessed.toml").write_text(toml_text, encoding="utf-8")
    cfgs = load_baselines(tmp_path)
    assert len(cfgs) == 1
    assert cfgs[0].id == "b1"
    assert cfgs[0].kind == "tested"
    assert cfgs[0].commands == [["-m", "pytest", "test/"], ["-m", "pytest", "extra/"]]


def test_load_baselines_legacy_command(tmp_path: Path) -> None:
    """load_baselines must also support the legacy single-list 'command' key."""
    toml_text = textwrap.dedent("""\
        [[baselines]]
        id = "b2"
        kind = "used"
        command = ["-m", "script"]
    """)
    (tmp_path / "witnessed.toml").write_text(toml_text, encoding="utf-8")
    cfgs = load_baselines(tmp_path)
    assert len(cfgs) == 1
    assert cfgs[0].commands == [["-m", "script"]]


# ---------------------------------------------------------------------------
# Full run_baselines on the fixture package
# ---------------------------------------------------------------------------


def test_levels_tested_used_unwitnessed(tmp_path: Path) -> None:
    """Three functions: one called by tests → tested, one by usage → used, one not called → unwitnessed."""
    repo_root, pkg_dir = _setup_fixture_repo(tmp_path)
    fixture_dir = repo_root / "fixture_pkg"

    toml_text = textwrap.dedent(f"""\
        [[baselines]]
        id = "tested"
        kind = "tested"
        commands = [
            ["-m", "pytest", "{(fixture_dir / 'test_fixture.py').as_posix()}", "-p", "no:cacheprovider", "-q"],
        ]

        [[baselines]]
        id = "used"
        kind = "used"
        commands = [
            ["{(fixture_dir / 'usage_script.py').as_posix()}"],
        ]
    """)
    (repo_root / "witnessed.toml").write_text(toml_text, encoding="utf-8")

    payload = run_baselines(repo_root=repo_root, package_dir=pkg_dir)

    units = payload["units"]
    # qualnames include "mypkg." prefix; look up by last component
    levels = {qn.split(".")[-1]: info["level"] for qn, info in units.items()}

    assert levels.get("suite_fn") == "tested", f"suite_fn level was {levels.get('suite_fn')!r}"
    assert levels.get("used_fn") == "used", f"used_fn level was {levels.get('used_fn')!r}"
    assert levels.get("untouched") == "unwitnessed", f"untouched level was {levels.get('untouched')!r}"


def test_used_beats_tested(tmp_path: Path) -> None:
    """A function seen by both tested and used baselines must keep level 'used'."""
    repo_root, pkg_dir = _setup_fixture_repo(tmp_path)
    fixture_dir = repo_root / "fixture_pkg"
    test_file = (fixture_dir / "test_fixture.py").as_posix()

    # Both baselines run the test suite (so suite_fn is seen by both).
    toml_text = textwrap.dedent(f"""\
        [[baselines]]
        id = "tested"
        kind = "tested"
        commands = [
            ["-m", "pytest", "{test_file}", "-p", "no:cacheprovider", "-q"],
        ]

        [[baselines]]
        id = "used"
        kind = "used"
        commands = [
            ["-m", "pytest", "{test_file}", "-p", "no:cacheprovider", "-q"],
        ]
    """)
    (repo_root / "witnessed.toml").write_text(toml_text, encoding="utf-8")

    payload = run_baselines(repo_root=repo_root, package_dir=pkg_dir)
    units = payload["units"]
    levels = {qn.split(".")[-1]: info["level"] for qn, info in units.items()}

    # suite_fn is seen by both; "used" baseline is stronger so level = "used".
    assert levels.get("suite_fn") == "used"


def test_non_zero_exit_recorded(tmp_path: Path) -> None:
    """A baseline that exits non-zero must have its exit_code recorded in the JSON."""
    repo_root, pkg_dir = _setup_fixture_repo(tmp_path)

    # Write a small script that always exits with code 42.
    fail_script = repo_root / "fail_with_42.py"
    fail_script.write_text("import sys\nsys.exit(42)\n", encoding="utf-8")

    toml_text = textwrap.dedent(f"""\
        [[baselines]]
        id = "bad"
        kind = "tested"
        commands = [
            ["{fail_script.as_posix()}"],
        ]
    """)
    (repo_root / "witnessed.toml").write_text(toml_text, encoding="utf-8")

    payload = run_baselines(repo_root=repo_root, package_dir=pkg_dir)
    rec = next(r for r in payload["baselines"] if r["id"] == "bad")
    assert rec["exit_code"] == 42


def test_write_baseline_json(tmp_path: Path) -> None:
    """write_baseline_json must persist a valid JSON file at .witnessed/baseline.json."""
    payload = {
        "generated_at": "2025-01-01T00:00:00+00:00",
        "commit": "abc",
        "baselines": [],
        "units": {},
    }
    out_path = write_baseline_json(tmp_path, payload)
    assert out_path == tmp_path / ".witnessed" / "baseline.json"
    loaded = json.loads(out_path.read_text(encoding="utf-8"))
    assert loaded["commit"] == "abc"


def test_subprocess_coverage(tmp_path: Path) -> None:
    """A function called only inside a subprocess.Popen child must be
    detected as observed (regression: baseline only measured the pytest
    process, missing functions exercised in child processes)."""
    # Package with two functions: one called directly, one only via subprocess.
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "def direct():\n    return 'direct'\n\n"
        "def via_subprocess():\n    return 'subprocess'\n",
        encoding="utf-8",
    )

    # A script that calls via_subprocess() -- this will be launched as a child.
    child_script = tmp_path / "child.py"
    child_script.write_text(
        "import sys\n"
        "sys.path.insert(0, r'" + str(tmp_path) + "')\n"
        "from mypkg import via_subprocess\n"
        "via_subprocess()\n",
        encoding="utf-8",
    )

    # The test suite: calls direct() directly and via_subprocess() via Popen.
    test_file = tmp_path / "test_sub.py"
    test_file.write_text(
        "import subprocess, sys\n"
        "import sys as _sys\n"
        "import pathlib\n"
        "_sys.path.insert(0, str(pathlib.Path(__file__).parent))\n"
        "from mypkg import direct\n"
        "\n"
        "def test_direct():\n"
        "    assert direct() == 'direct'\n"
        "\n"
        "def test_via_subprocess():\n"
        "    r = subprocess.run(\n"
        "        [sys.executable, r'" + str(child_script) + "'],\n"
        "        capture_output=True,\n"
        "    )\n"
        "    assert r.returncode == 0\n",
        encoding="utf-8",
    )

    (tmp_path / "witnessed.toml").write_text(
        "[[ baselines ]]\n"
        'id = "tested"\n'
        'kind = "tested"\n'
        "commands = [\n"
        f'    ["-m", "pytest", "{test_file.as_posix()}", "-p", "no:cacheprovider", "-q"],\n'
        "]\n",
        encoding="utf-8",
    )

    payload = run_baselines(repo_root=tmp_path, package_dir=pkg)
    units = payload["units"]
    levels = {qn.split(".")[-1]: info["level"] for qn, info in units.items()}

    assert levels.get("direct") == "tested", (
        f"direct() should be tested, got {levels.get('direct')!r}"
    )
    assert levels.get("via_subprocess") == "tested", (
        f"via_subprocess() should be tested (subprocess coverage), "
        f"got {levels.get('via_subprocess')!r}"
    )
