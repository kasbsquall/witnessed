"""Adversarial and honest tests for witnessed.gate.

One test per rejection reason, plus one honest witness that must pass.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from witnessed.gate import run_gate


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pkg(tmp_path: Path) -> tuple[Path, str]:
    """Create a small package ``mypkg`` with a single function ``add``.

    Returns (pkg_dir, qualname).
    The package is installed into sys.path via conftest / direct path injection.
    """
    pkg = tmp_path / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def add(a, b):
                return a + b
        """),
        encoding="utf-8",
    )
    return pkg, "mypkg.add"


def _make_scan_json(tmp_path: Path, qualname: str, pkg: Path) -> Path:
    """Write a minimal .witnessed/scan.json so run_gate can find the unit."""
    import ast
    import json

    init_py = pkg / "__init__.py"
    source = init_py.read_text(encoding="utf-8")
    tree = ast.parse(source)
    func = next(
        n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        and n.name == qualname.split(".")[-1]
    )
    rel_file = init_py.relative_to(tmp_path).as_posix()

    witnessed_dir = tmp_path / ".witnessed"
    witnessed_dir.mkdir(exist_ok=True)
    scan = {
        "base": "base",
        "head": "head",
        "changed": [
            {
                "qualname": qualname,
                "file": rel_file,
                "change": "modified",
                "level": "unwitnessed",
                "seen_by": [],
                "body_start": func.body[0].lineno,
                "body_end": func.end_lineno,
            }
        ],
        "counts": {"used": 0, "tested": 0, "agent_witnessed": 0, "unwitnessed": 1},
    }
    scan_path = witnessed_dir / "scan.json"
    scan_path.write_text(json.dumps(scan, indent=2), encoding="utf-8")
    return scan_path


def _run(tmp_path: Path, witness_src: str, qualname: str | None = None) -> dict:
    """Write a witness file and run the gate, returning the verdict dict."""
    pkg, default_qualname = _make_pkg(tmp_path)
    qn = qualname or default_qualname
    scan_path = _make_scan_json(tmp_path, qn, pkg)

    witness_path = tmp_path / "witness.py"
    witness_path.write_text(textwrap.dedent(witness_src), encoding="utf-8")

    return run_gate(
        witness_path=witness_path,
        qualname=qn,
        repo_root=tmp_path,
        scan_json_path=scan_path,
    )


# ---------------------------------------------------------------------------
# Honest witness — must pass
# ---------------------------------------------------------------------------


def test_honest_witness_passes(tmp_path: Path) -> None:
    """An honest, complete witness must be accepted."""
    # Insert tmp_path into sys.path so mypkg can be imported.
    sys.path.insert(0, str(tmp_path))
    try:
        verdict = _run(
            tmp_path,
            f"""\
                import sys
                sys.path.insert(0, {str(tmp_path)!r})
                import mypkg
                result = mypkg.add(2, 3)
                assert result == 5
            """,
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert verdict["accepted"] is True, f"expected accepted, got reason={verdict['reason']!r}"
    assert verdict["reason"] is None
    assert verdict["body_lines_executed"], "body lines must be non-empty on accept"


# ---------------------------------------------------------------------------
# nonzero_exit
# ---------------------------------------------------------------------------


def test_reject_nonzero_exit(tmp_path: Path) -> None:
    """A witness that raises an uncaught exception must be rejected with nonzero_exit."""
    verdict = _run(
        tmp_path,
        f"""\
            import sys
            sys.path.insert(0, {str(tmp_path)!r})
            import mypkg
            result = mypkg.add(1, 2)
            assert result == 3
            raise RuntimeError("deliberate failure")
        """,
    )
    assert not verdict["accepted"]
    assert verdict["reason"] == "nonzero_exit"


# ---------------------------------------------------------------------------
# timeout
# ---------------------------------------------------------------------------


def test_reject_timeout(tmp_path: Path) -> None:
    """A witness that hangs longer than the timeout must be rejected with timeout."""
    import witnessed.gate as gate_module

    orig = gate_module._TIMEOUT_SECONDS
    gate_module._TIMEOUT_SECONDS = 1  # shorten to 1 s for the test
    try:
        verdict = _run(
            tmp_path,
            f"""\
                import sys, time
                sys.path.insert(0, {str(tmp_path)!r})
                import mypkg
                result = mypkg.add(1, 2)
                assert result == 3
                time.sleep(60)
            """,
        )
    finally:
        gate_module._TIMEOUT_SECONDS = orig

    assert not verdict["accepted"]
    assert verdict["reason"] == "timeout"


# ---------------------------------------------------------------------------
# body_not_executed
# ---------------------------------------------------------------------------


def test_reject_body_not_executed(tmp_path: Path) -> None:
    """A witness that imports but never calls the target must be rejected with body_not_executed."""
    # The witness calls a different function, not mypkg.add, so the body is never run.
    # It must also pass AST checks (has a call site and an assert), so we fake-call
    # by calling a local function named add and asserting on it.  The body_not_executed
    # check fires because the real mypkg.add body never executes.
    verdict = _run(
        tmp_path,
        f"""\
            import sys
            sys.path.insert(0, {str(tmp_path)!r})
            import mypkg

            def add(a, b):
                return a + b

            result = mypkg.add(1, 2)
            assert result == 3
        """,
    )
    # The honest witness above WILL execute the body; we need a case where it doesn't.
    # Use a witness that exits 0 but the target file has no coverage.
    # Simplest: patch scan.json with body_start/body_end pointing to non-existent lines.
    import json

    scan_path = tmp_path / ".witnessed" / "scan.json"
    scan = json.loads(scan_path.read_text())
    for rec in scan["changed"]:
        rec["body_start"] = 9999
        rec["body_end"] = 9999
    scan_path.write_text(json.dumps(scan))

    witness_path = tmp_path / "witness_nobody.py"
    witness_path.write_text(
        textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(tmp_path)!r})
            import mypkg
            result = mypkg.add(1, 2)
            assert result == 3
        """),
        encoding="utf-8",
    )

    verdict2 = run_gate(
        witness_path=witness_path,
        qualname="mypkg.add",
        repo_root=tmp_path,
        scan_json_path=scan_path,
    )
    assert not verdict2["accepted"]
    assert verdict2["reason"] == "body_not_executed"


# ---------------------------------------------------------------------------
# target_modified: witness rewrites the target file and restores it
# ---------------------------------------------------------------------------


def test_reject_target_modified(tmp_path: Path) -> None:
    """A witness that rewrites the target file and restores it must fail target_modified.

    Even though the final SHA-256 matches (content restored), the gate detects
    that the file's mtime advanced during the run.
    """
    pkg, qualname = _make_pkg(tmp_path)
    scan_path = _make_scan_json(tmp_path, qualname, pkg)

    target_file = pkg / "__init__.py"

    witness_path = tmp_path / "witness_modify.py"
    witness_path.write_text(
        textwrap.dedent(f"""\
            import sys
            sys.path.insert(0, {str(tmp_path)!r})
            import mypkg, pathlib

            # Rewrite the target file, then restore original content.
            # The SHA-256 is unchanged, but mtime advances.
            p = pathlib.Path({str(target_file)!r})
            original = p.read_text(encoding="utf-8")
            p.write_text(original + "\\n# temp\\n", encoding="utf-8")
            p.write_text(original, encoding="utf-8")

            result = mypkg.add(1, 2)
            assert result == 3
        """),
        encoding="utf-8",
    )

    verdict = run_gate(
        witness_path=witness_path,
        qualname=qualname,
        repo_root=tmp_path,
        scan_json_path=scan_path,
    )
    assert not verdict["accepted"]
    assert verdict["reason"] == "target_modified"


# ---------------------------------------------------------------------------
# no_call_site: witness only imports the function, never calls it
# ---------------------------------------------------------------------------


def test_reject_no_call_site(tmp_path: Path) -> None:
    """A witness that only imports the function without calling it must fail no_call_site.

    The witness calls via getattr so the body executes (body_not_executed does not
    fire) but there is no syntactic call site matching the qualname (no_call_site fires).
    """
    verdict = _run(
        tmp_path,
        f"""\
            import sys
            sys.path.insert(0, {str(tmp_path)!r})
            import mypkg

            # Call via getattr — body executes but no syntactic call site.
            fn = getattr(mypkg, "add")
            result = fn(1, 2)
            assert result == 3
        """,
    )
    assert not verdict["accepted"]
    assert verdict["reason"] == "no_call_site"


# ---------------------------------------------------------------------------
# patches_target: witness assigns module attribute
# ---------------------------------------------------------------------------


def test_reject_patches_target(tmp_path: Path) -> None:
    """A witness that monkeypatches the target module must fail patches_target.

    The real call is made first (so body_not_executed does not fire), then the
    module attribute is overwritten.  patches_target fires on the AST check.
    """
    verdict = _run(
        tmp_path,
        f"""\
            import sys
            sys.path.insert(0, {str(tmp_path)!r})
            import mypkg

            # Call the real function first so the body executes.
            result = mypkg.add(1, 2)
            assert result == 3

            # Now patch the module attribute — this is what the gate must catch.
            mypkg.add = lambda a, b: a + b
        """,
    )
    assert not verdict["accepted"]
    assert verdict["reason"] == "patches_target"


# ---------------------------------------------------------------------------
# no_assertion: witness calls the target but never asserts on its return value
# ---------------------------------------------------------------------------


def test_reject_no_assertion(tmp_path: Path) -> None:
    """A witness that calls target but asserts nothing must fail no_assertion."""
    verdict = _run(
        tmp_path,
        f"""\
            import sys
            sys.path.insert(0, {str(tmp_path)!r})
            import mypkg

            result = mypkg.add(1, 2)
            print(result)
        """,
    )
    assert not verdict["accepted"]
    assert verdict["reason"] == "no_assertion"


# ---------------------------------------------------------------------------
# scan.json is updated to agent_witnessed on accept
# ---------------------------------------------------------------------------


def test_scan_json_updated_on_accept(tmp_path: Path) -> None:
    """On acceptance the unit's level in scan.json must become agent_witnessed."""
    import json

    sys.path.insert(0, str(tmp_path))
    try:
        verdict = _run(
            tmp_path,
            f"""\
                import sys
                sys.path.insert(0, {str(tmp_path)!r})
                import mypkg
                result = mypkg.add(10, 20)
                assert result == 30
            """,
        )
    finally:
        sys.path.remove(str(tmp_path))

    assert verdict["accepted"], f"expected accepted, got reason={verdict['reason']!r}"

    scan_path = tmp_path / ".witnessed" / "scan.json"
    data = json.loads(scan_path.read_text())
    levels = {rec["qualname"]: rec["level"] for rec in data["changed"]}
    assert levels.get("mypkg.add") == "agent_witnessed"
    assert data["counts"]["agent_witnessed"] == 1
    assert data["counts"]["unwitnessed"] == 0
