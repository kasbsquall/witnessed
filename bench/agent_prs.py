"""How often does a pull request written by a coding agent touch functions its own tests never run?

For each merged pull request authored by a coding agent (listed in a TSV of
"number<TAB>merge commit"), checks out the merge commit, asks Witnessed's own
library which functions the pull request added or modified
(witnessed.diff.changed_units against the merge commit's first parent) and
where their bodies are (witnessed.units.enumerate_units), runs the project's
own test suite at that commit under coverage, subprocesses included, and lists
the changed functions whose body never executed.

Written by Claude (Anthropic) as an analysis script for this repository, not by
IBM Bob. Like bench/history.py it measures only the "tested" level.

Usage:
    python bench/agent_prs.py <clone> <prs.tsv> --package sigma --tests tests --out bench/agent_prs.json
The interpreter running this script must have the target project's
dependencies installed; the project itself is imported from each checkout.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from coverage import CoverageData  # noqa: E402

from witnessed.diff import changed_units  # noqa: E402
from witnessed.units import enumerate_units  # noqa: E402

TIMEOUT_S = 900
PER_TEST_TIMEOUT_S = 60  # needs pytest-timeout


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


def executed_lines(tree: Path, package: str, tests: str) -> tuple[dict[str, set[int]], str]:
    rc = tree / ".bench-coveragerc"
    data = tree / ".bench-coverage"
    rc.write_text("[run]\nparallel = true\npatch = subprocess\n"
                  f"source = {(tree / package).as_posix()}\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(tree)}
    result = subprocess.run(
        [sys.executable, "-m", "coverage", "run", f"--rcfile={rc}", f"--data-file={data}",
         "-m", "pytest", tests, "-q", "-p", "no:cacheprovider", "--tb=no", "-o", "addopts=",
         f"--timeout={PER_TEST_TIMEOUT_S}", "--continue-on-collection-errors"],
        cwd=tree, capture_output=True, text=True, timeout=TIMEOUT_S, env=env)
    if "Timeout" in result.stdout + result.stderr:
        raise TimeoutError("a test exceeded the per-test timeout; suite cut short")
    subprocess.run([sys.executable, "-m", "coverage", "combine", f"--rcfile={rc}",
                    f"--data-file={data}"], cwd=tree, capture_output=True, text=True)
    cov = CoverageData(basename=str(data))
    cov.read()
    lines = {str(Path(f).resolve()): set(cov.lines(f) or []) for f in cov.measured_files()}
    summary = (result.stdout.strip().splitlines() or [""])[-1]
    return lines, summary


def scan_pr(upstream: Path, number: str, commit: str, package: str, tests: str) -> dict:
    tree = Path(tempfile.mkdtemp(prefix="agentpr-"))
    record: dict = {"pr": int(number), "commit": commit}
    try:
        git("worktree", "add", "--detach", str(tree), commit, cwd=upstream)
        changed = changed_units(base=f"{commit}^1", head=commit, repo_root=tree,
                                package_dir=tree / package)
        record["changed"] = [cu.qualname for cu in changed]
        if not changed:
            return record
        units = {u.qualname: u for u in enumerate_units(tree / package, repo_root=tree)}
        lines, summary = executed_lines(tree, package, tests)
        never = []
        for cu in changed:
            unit = units.get(cu.qualname)
            if unit is None:
                continue
            ran = lines.get(str((tree / unit.file).resolve()), set())
            if not ran & set(range(unit.body_start, unit.body_end + 1)):
                never.append(cu.qualname)
        record.update(never=never, tests=summary)
        return record
    except TimeoutError as exc:
        record["skipped"] = str(exc)
        return record
    finally:
        git("worktree", "remove", "--force", str(tree), cwd=upstream)
        shutil.rmtree(tree, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("prs", type=Path, help="TSV: pull request number, merge commit, ...")
    parser.add_argument("--package", required=True)
    parser.add_argument("--tests", default="tests")
    parser.add_argument("--out", type=Path, default=REPO / "bench" / "agent_prs.json")
    args = parser.parse_args()

    records = []
    for row in args.prs.read_text(encoding="utf-8").splitlines():
        number, commit = row.split("\t")[:2]
        rec = scan_pr(args.upstream, number, commit, args.package, args.tests)
        records.append(rec)
        print(f"#{rec['pr']}: {len(rec.get('changed', []))} changed, "
              f"never ran: {rec.get('never', rec.get('skipped', '-'))}", flush=True)

    measured = [r for r in records if r.get("changed") and "skipped" not in r]
    summary = {
        "pull_requests": len(records),
        "with_changed_functions": len(measured),
        "skipped": sum(1 for r in records if "skipped" in r),
        "flagged": sum(1 for r in measured if r["never"]),
        "changed_functions": sum(len(r["changed"]) for r in measured),
        "changed_functions_never_run": sum(len(r["never"]) for r in measured),
    }
    args.out.write_text(json.dumps({"summary": summary, "records": records}, indent=1), encoding="utf-8")
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
