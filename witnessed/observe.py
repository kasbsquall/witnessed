"""Run baselines under coverage and produce .witnessed/baseline.json."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from coverage import CoverageData

from .units import Unit, enumerate_units

Level = Literal["used", "tested", "unwitnessed"]

_STRENGTH: dict[Level, int] = {
    "used": 3,
    "tested": 2,
    "unwitnessed": 0,
}


@dataclass
class BaselineCfg:
    id: str
    kind: Literal["used", "tested"]
    commands: list[list[str]]  # one or more argv lists to run under this baseline
    cwd: Path | None = None    # working directory for subprocess (default: repo_root)


def load_baselines(repo_root: Path) -> list[BaselineCfg]:
    """Parse *repo_root*/witnessed.toml and return the configured baselines."""
    toml_path = repo_root / "witnessed.toml"
    with toml_path.open("rb") as fh:
        data = tomllib.load(fh)
    result: list[BaselineCfg] = []
    for entry in data.get("baselines", []):
        # Support both "commands" (list of lists) and legacy "command" (single list).
        if "commands" in entry:
            cmds = entry["commands"]
        else:
            cmds = [entry["command"]]
        cwd = Path(entry["cwd"]) if "cwd" in entry else None
        result.append(
            BaselineCfg(
                id=entry["id"],
                kind=entry["kind"],
                commands=cmds,
                cwd=cwd,
            )
        )
    return result


def _run_baseline(
    cfg: BaselineCfg,
    repo_root: Path,
    package_dir: Path,
) -> tuple[int, Path]:
    """Run all commands in *cfg* under coverage.py and return (exit_code, cov_file).

    All commands share the same coverage data file; the returned exit_code is
    the first non-zero code encountered, or 0 if all commands succeed.

    Subprocess measurement is enabled via a temporary rcfile that sets
    ``parallel = true`` and ``patch = subprocess``.  In parallel mode each
    ``coverage run`` invocation writes its data to a suffixed file next to the
    base data file.  After all commands finish, ``coverage combine`` merges all
    those files -- including any written by child processes -- into the single
    final data file.
    """
    witnessed_dir = repo_root / ".witnessed"
    witnessed_dir.mkdir(exist_ok=True)
    cov_file = witnessed_dir / f"{cfg.id}.coverage"

    run_cwd = (repo_root / cfg.cwd).resolve() if cfg.cwd is not None else repo_root
    overall_exit = 0

    # Write a temporary rcfile so that child processes launched by the baseline
    # (e.g. via subprocess.Popen) are also measured.
    rcfile_content = (
        "[run]\n"
        f"source = {package_dir}\n"
        "parallel = true\n"
        "patch = subprocess\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ini", delete=False, encoding="utf-8"
    ) as tf:
        tf.write(rcfile_content)
        rcfile = tf.name

    try:
        for cmd_args in cfg.commands:
            # In parallel mode coverage run always writes a new suffixed file;
            # do not use --append (it is incompatible with parallel mode).
            coverage_cmd = [
                sys.executable,
                "-m",
                "coverage",
                "run",
                f"--rcfile={rcfile}",
                f"--data-file={cov_file}",
            ]
            coverage_cmd.extend(cmd_args)

            result = subprocess.run(coverage_cmd, cwd=run_cwd)
            if result.returncode != 0 and overall_exit == 0:
                overall_exit = result.returncode

        # Merge all parallel data files (from this process and subprocesses)
        # into the single final data file.
        subprocess.run(
            [
                sys.executable,
                "-m",
                "coverage",
                "combine",
                f"--rcfile={rcfile}",
                f"--data-file={cov_file}",
            ],
            cwd=run_cwd,
            capture_output=True,
        )
    finally:
        Path(rcfile).unlink(missing_ok=True)

    return overall_exit, cov_file


def _observed_units(
    cov_file: Path,
    units: list[Unit],
    repo_root: Path,
) -> set[str]:
    """Return the set of qualnames whose body was touched in *cov_file*."""
    cov = CoverageData(basename=str(cov_file))
    cov.read()

    # coverage stores absolute paths; build a mapping from absolute path →
    # frozenset of executed line numbers.
    executed: dict[str, frozenset[int]] = {}
    for abs_path in cov.measured_files():
        lines = cov.lines(abs_path)
        if lines:
            executed[abs_path] = frozenset(lines)

    observed: set[str] = set()
    for unit in units:
        abs_path = str((repo_root / unit.file).resolve())
        hit_lines = executed.get(abs_path, frozenset())
        body_range = range(unit.body_start, unit.body_end + 1)
        if hit_lines.intersection(body_range):
            observed.add(unit.qualname)
    return observed


def _git_commit(repo_root: Path) -> str:
    """Return the current HEAD commit SHA, or 'unknown' on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def run_baselines(
    repo_root: Path,
    package_dir: Path,
) -> dict:
    """Run all baselines from witnessed.toml and return the baseline.json payload."""
    repo_root = repo_root.resolve()
    package_dir = package_dir.resolve()
    cfgs = load_baselines(repo_root)
    units = enumerate_units(package_dir, repo_root=repo_root)

    # For each unit track the strongest level seen and which baselines saw it.
    levels: dict[str, int] = {u.qualname: 0 for u in units}  # strength
    seen_by: dict[str, list[str]] = {u.qualname: [] for u in units}

    baseline_records = []

    for cfg in cfgs:
        exit_code, cov_file = _run_baseline(cfg, repo_root, package_dir)
        if exit_code != 0:
            print(
                f"WARNING: baseline '{cfg.id}' exited with code {exit_code}",
                file=sys.stderr,
            )

        observed = _observed_units(cov_file, units, repo_root)
        strength = _STRENGTH[cfg.kind]

        for qualname in observed:
            if strength > levels[qualname]:
                levels[qualname] = strength
            seen_by[qualname].append(cfg.id)

        baseline_records.append(
            {
                "id": cfg.id,
                "kind": cfg.kind,
                "exit_code": exit_code,
                "observed": sorted(observed),
            }
        )

    # Build units dict.
    units_out: dict[str, dict] = {}
    for unit in units:
        strength = levels[unit.qualname]
        if strength == 3:
            level: Level = "used"
        elif strength == 2:
            level = "tested"
        else:
            level = "unwitnessed"

        units_out[unit.qualname] = {
            "file": unit.file,
            "body_start": unit.body_start,
            "body_end": unit.body_end,
            "level": level,
            "seen_by": seen_by[unit.qualname],
        }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": _git_commit(repo_root),
        "baselines": baseline_records,
        "units": units_out,
    }


def write_baseline_json(repo_root: Path, payload: dict) -> Path:
    """Write *payload* to .witnessed/baseline.json and return the path."""
    out_path = repo_root / ".witnessed" / "baseline.json"
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return out_path
