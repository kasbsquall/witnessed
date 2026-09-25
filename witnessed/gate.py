"""Gate: validate a witness file and promote a unit to agent_witnessed."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Literal

from coverage import CoverageData

RejectionReason = Literal[
    "nonzero_exit",
    "timeout",
    "body_not_executed",
    "target_modified",
    "no_call_site",
    "patches_target",
    "no_assertion",
]

# Rules evaluated in this fixed order; first failure wins.
_RULE_ORDER: list[RejectionReason] = [
    "nonzero_exit",
    "timeout",
    "body_not_executed",
    "target_modified",
    "no_call_site",
    "patches_target",
    "no_assertion",
]

_TIMEOUT_SECONDS = 30


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_name(qualname: str) -> str:
    """Return the top-level package name from a qualname like 'tabulate._is_file'."""
    return qualname.split(".")[0]


def _function_name(qualname: str) -> str:
    """Return the final component of a qualname."""
    return qualname.split(".")[-1]


def _is_target_call(node: ast.expr, qualname: str) -> bool:
    """Return True if *node* is a call to the target identified by *qualname*.

    Handles:
    - ``pkg.func(...)``         — attribute chain matching qualname
    - ``func(...)``             — bare name matching the last component
    - ``obj.method(...)``       — method call matching the last component
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # Direct attribute chain: tabulate._is_file(...)
    if _call_matches_qualname(func, qualname):
        return True
    # Bare name or method call matching the last component
    fname = _function_name(qualname)
    if isinstance(func, ast.Name) and func.id == fname:
        return True
    if isinstance(func, ast.Attribute) and func.attr == fname:
        return True
    return False


def _call_matches_qualname(node: ast.expr, qualname: str) -> bool:
    """Check if *node* (the func of a Call) matches the dotted *qualname*."""
    parts = qualname.split(".")
    # Walk the attribute chain right-to-left.
    for part in reversed(parts):
        if isinstance(node, ast.Attribute):
            if node.attr != part:
                return False
            node = node.value  # type: ignore[assignment]
        elif isinstance(node, ast.Name):
            return node.id == part and part == parts[0]
        else:
            return False
    return True


def _find_target_calls(tree: ast.AST, qualname: str) -> list[ast.Call]:
    """Return all Call nodes in *tree* that invoke the target."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _is_target_call(node, qualname)
    ]


def _has_call_site(witness_source: str, qualname: str) -> bool:
    """Return True if the witness source calls the target."""
    try:
        tree = ast.parse(witness_source)
    except SyntaxError:
        return False
    return bool(_find_target_calls(tree, qualname))


def _patches_target(witness_source: str, qualname: str) -> bool:
    """Return True if the witness assigns attributes of the target module.

    Detects:
    - ``mod.attr = ...``   (Assign / AugAssign / AnnAssign with an Attribute target)
    - ``setattr(mod, ...)``
    """
    pkg = _package_name(qualname)
    try:
        tree = ast.parse(witness_source)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        # mod.attr = value
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if _is_module_attr_set(t, pkg):
                    return True
        elif isinstance(node, ast.AugAssign):
            if _is_module_attr_set(node.target, pkg):
                return True
        elif isinstance(node, ast.AnnAssign):
            if node.value is not None and _is_module_attr_set(node.target, pkg):
                return True
        # setattr(mod, ...) or monkeypatch.setattr(...)
        elif isinstance(node, ast.Call):
            if _is_setattr_on_module(node, pkg):
                return True
    return False


def _is_module_attr_set(target: ast.expr, pkg: str) -> bool:
    """Return True if *target* is an attribute assignment on the package module."""
    return (
        isinstance(target, ast.Attribute)
        and isinstance(target.value, ast.Name)
        and target.value.id == pkg
    )


def _is_setattr_on_module(call: ast.Call, pkg: str) -> bool:
    """Return True if *call* is setattr(<pkg>, ...) or x.setattr(<pkg>, ...)."""
    func = call.func
    # setattr(mod, ...)
    if isinstance(func, ast.Name) and func.id == "setattr":
        if call.args and isinstance(call.args[0], ast.Name):
            return call.args[0].id == pkg
    # monkeypatch.setattr(mod, ...) — first arg is the module name
    if isinstance(func, ast.Attribute) and func.attr == "setattr":
        if call.args and isinstance(call.args[0], ast.Name):
            return call.args[0].id == pkg
    return False


def _has_assertion_on_return(witness_source: str, qualname: str) -> bool:
    """Return True if the witness has an assert that uses the target's return value.

    Two patterns are accepted:
    1. Direct: ``assert target_call(...) ...``
    2. Indirect: ``result = target_call(...); assert result ...``
    """
    try:
        tree = ast.parse(witness_source)
    except SyntaxError:
        return False

    target_calls = _find_target_calls(tree, qualname)
    if not target_calls:
        return False

    # Collect Names that are directly assigned from a target call.
    # Pattern: x = target(...)  (simple assignment, one target)
    assigned_from_call: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                if isinstance(node.value, ast.Call) and _is_target_call(node.value, qualname):
                    assigned_from_call.add(node.targets[0].id)

    # Check assert statements.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            test = node.test
            # Pattern 1: assert contains a direct call to target.
            for sub in ast.walk(test):
                if isinstance(sub, ast.Call) and _is_target_call(sub, qualname):
                    return True
            # Pattern 2: assert references a variable assigned from target.
            for sub in ast.walk(test):
                if isinstance(sub, ast.Name) and sub.id in assigned_from_call:
                    return True

    return False


def _body_lines_executed(
    cov_file: Path,
    target_file: Path,
    body_start: int,
    body_end: int,
) -> list[int]:
    """Return body lines of the target that were executed according to *cov_file*."""
    cov = CoverageData(basename=str(cov_file))
    try:
        cov.read()
    except Exception:
        return []

    abs_path = str(target_file.resolve())
    # Coverage stores absolute paths; try direct key first, then case-normalised.
    lines = cov.lines(abs_path)
    if lines is None:
        # Try to find by suffix match (handles minor path differences).
        for measured in cov.measured_files():
            if Path(measured).resolve() == target_file.resolve():
                lines = cov.lines(measured)
                break
    if not lines:
        return []

    body_range = set(range(body_start, body_end + 1))
    return sorted(l for l in lines if l in body_range)


def run_gate(
    witness_path: Path,
    qualname: str,
    repo_root: Path,
    scan_json_path: Path | None = None,
) -> dict:
    """Run all gate rules for *witness_path* against *qualname*.

    Returns a verdict dict with keys:
      target, witness, accepted, reason (or None), body_lines_executed.

    Writes the verdict to ``.witnessed/gate/<qualname>.json``.
    When accepted, updates the unit's level in ``.witnessed/scan.json``.
    """
    repo_root = repo_root.resolve()
    witness_path = witness_path.resolve()

    # Load scan.json to find the unit's file, body_start, body_end.
    if scan_json_path is None:
        scan_json_path = repo_root / ".witnessed" / "scan.json"

    scan_data: dict = {}
    unit_info: dict = {}
    if scan_json_path.exists():
        scan_data = json.loads(scan_json_path.read_text(encoding="utf-8"))
        # scan.json has "changed" list; find the unit.
        for rec in scan_data.get("changed", []):
            if rec.get("qualname") == qualname:
                unit_info = rec
                break

    # Determine the target file path.
    target_file: Path | None = None
    body_start: int = 0
    body_end: int = 0
    if unit_info:
        rel_file = unit_info.get("file", "")
        if rel_file:
            target_file = repo_root / rel_file
        body_start = unit_info.get("body_start", 0)
        body_end = unit_info.get("body_end", 0)

    # Also try baseline.json if not found in scan.json.
    if target_file is None or not target_file.exists():
        baseline_path = repo_root / ".witnessed" / "baseline.json"
        if baseline_path.exists():
            baseline_data = json.loads(baseline_path.read_text(encoding="utf-8"))
            unit_rec = baseline_data.get("units", {}).get(qualname, {})
            if unit_rec:
                rel_file = unit_rec.get("file", "")
                if rel_file:
                    target_file = repo_root / rel_file
                body_start = unit_rec.get("body_start", 0)
                body_end = unit_rec.get("body_end", 0)

    pkg_name = _package_name(qualname)
    witness_source = witness_path.read_text(encoding="utf-8")

    # Rejection flags, evaluated in order.
    failures: dict[RejectionReason, bool] = {r: False for r in _RULE_ORDER}

    # --- SHA-256 and mtime before run ---
    sha_before: str | None = None
    mtime_before: float | None = None
    if target_file and target_file.exists():
        sha_before = _sha256(target_file)
        mtime_before = target_file.stat().st_mtime

    # --- Rule 5: patches_target (AST, before run) ---
    if _patches_target(witness_source, qualname):
        failures["patches_target"] = True

    # --- Rule 4: no_call_site (AST, before run) ---
    if not _has_call_site(witness_source, qualname):
        failures["no_call_site"] = True

    # --- Rule 7: no_assertion (AST, before run) ---
    if not _has_assertion_on_return(witness_source, qualname):
        failures["no_assertion"] = True

    # --- Rules 1 & 2: run under coverage ---
    timed_out = False
    exit_code: int = -1
    body_lines: list[int] = []

    with tempfile.TemporaryDirectory() as tmp_dir:
        cov_file = Path(tmp_dir) / "witness.coverage"

        cmd = [
            sys.executable,
            "-m", "coverage", "run",
            f"--data-file={cov_file}",
            f"--source={pkg_name}",
            str(witness_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                cwd=repo_root,
                timeout=_TIMEOUT_SECONDS,
                capture_output=True,
            )
            exit_code = result.returncode
        except subprocess.TimeoutExpired:
            timed_out = True

        if timed_out:
            failures["timeout"] = True
        elif exit_code != 0:
            failures["nonzero_exit"] = True
        else:
            # Rule 3: check body coverage.
            if target_file and target_file.exists() and body_start and body_end:
                body_lines = _body_lines_executed(
                    cov_file, target_file, body_start, body_end
                )
                if not body_lines:
                    failures["body_not_executed"] = True

    # --- Rule 3: target_modified (SHA-256 and mtime after run) ---
    # Catches both permanent modifications (SHA-256 differs) and write-then-restore
    # (mtime advanced even though content was restored).
    if sha_before is not None and target_file and target_file.exists():
        sha_after = _sha256(target_file)
        mtime_after = target_file.stat().st_mtime
        if sha_after != sha_before or mtime_after != mtime_before:
            failures["target_modified"] = True

    # --- Determine verdict (first failing rule in fixed order) ---
    first_failure: RejectionReason | None = None
    for reason in _RULE_ORDER:
        if failures[reason]:
            first_failure = reason
            break

    accepted = first_failure is None

    verdict: dict = {
        "target": qualname,
        "witness": str(witness_path.relative_to(repo_root).as_posix()),
        "accepted": accepted,
        "reason": first_failure,
        "body_lines_executed": body_lines,
    }

    # --- Write verdict JSON ---
    gate_dir = repo_root / ".witnessed" / "gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    # Sanitise qualname for use as filename (replace dots with underscores).
    safe_name = qualname.replace(".", "_")
    verdict_path = gate_dir / f"{safe_name}.json"
    verdict_path.write_text(json.dumps(verdict, indent=2), encoding="utf-8")

    # --- Update scan.json when accepted ---
    if accepted and scan_json_path.exists():
        _update_scan_json(scan_json_path, qualname)

    return verdict


def _update_scan_json(scan_json_path: Path, qualname: str) -> None:
    """Set the unit's level to agent_witnessed in scan.json and recompute counts."""
    data = json.loads(scan_json_path.read_text(encoding="utf-8"))

    updated = False
    for rec in data.get("changed", []):
        if rec.get("qualname") == qualname:
            rec["level"] = "agent_witnessed"
            updated = True
            break

    if not updated:
        return

    # Recompute counts.
    counts: dict[str, int] = {"used": 0, "tested": 0, "agent_witnessed": 0, "unwitnessed": 0}
    for rec in data.get("changed", []):
        level = rec.get("level", "unwitnessed")
        if level in counts:
            counts[level] += 1

    data["counts"] = counts
    scan_json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
