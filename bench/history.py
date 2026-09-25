"""How often does a real change touch functions its own test suite never runs?

Walks the history of an upstream python-tabulate clone and, for every
non-merge commit that changes the package, asks Witnessed's own library which
functions the commit added or modified (witnessed.diff.changed_units) and
where their bodies are (witnessed.units.enumerate_units). It then runs that
commit's own test suite under coverage, subprocesses included, and counts the
changed functions whose body never executed.

Written by Claude (Anthropic) as an analysis script for this repository, not by
IBM Bob. It measures only the "tested" level: tabulate's history has no
real-use baseline.

Usage:
    python bench/history.py <path to a full python-tabulate clone> [--since 2022-05-20] [--until 268615a]
Writes bench/history.json and prints a summary.
"""
from __future__ import annotations

import argparse
import json
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

TIMEOUT_S = 300
PER_TEST_TIMEOUT_S = 30  # needs pytest-timeout


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", check=True).stdout


def executed_lines(tree: Path) -> tuple[dict[str, set[int]], str]:
    """Run the commit's tests under coverage, subprocesses included."""
    rc = tree / ".bench-coveragerc"
    data = tree / ".bench-coverage"
    rc.write_text("[run]\nparallel = true\npatch = subprocess\n"
                  f"source = {(tree / 'tabulate').as_posix()}\n", encoding="utf-8")
    # Two wrapping tests hang at some October 2024 commits (also with the wcwidth
    # of that time), so they are deselected. The per-test timeout is a safety net:
    # on Windows it ends the whole run, so a commit whose suite was cut short is
    # reported as skipped instead of being counted with partial coverage.
    result = subprocess.run(
        [sys.executable, "-m", "coverage", "run", f"--rcfile={rc}", f"--data-file={data}",
         "-m", "pytest", "test", "-q", "-p", "no:cacheprovider", "--tb=no", "-o", "addopts=",
         f"--timeout={PER_TEST_TIMEOUT_S}",
         "--deselect", "test/test_internal.py::test_wrap_text_wide_chars",
         "--deselect", "test/test_textwrapper.py::test_wrap_mixed_string"],
        cwd=tree, capture_output=True, text=True, timeout=TIMEOUT_S)
    if "Timeout" in result.stdout + result.stderr:
        raise TimeoutError("a test exceeded the per-test timeout; suite cut short")
    subprocess.run([sys.executable, "-m", "coverage", "combine", f"--rcfile={rc}",
                    f"--data-file={data}"], cwd=tree, capture_output=True, text=True)
    cov = CoverageData(basename=str(data))
    cov.read()
    lines = {str(Path(f).resolve()): set(cov.lines(f) or []) for f in cov.measured_files()}
    summary = (result.stdout.strip().splitlines() or [""])[-1]
    return lines, summary


def scan_commit(upstream: Path, commit: str) -> dict:
    tree = Path(tempfile.mkdtemp(prefix="bench-"))
    try:
        # changed_units reads head functions from the working tree, as `witnessed scan` does,
        # so each commit is checked out in its own worktree first.
        git("worktree", "add", "--detach", str(tree), commit, cwd=upstream)
        changed = changed_units(base=f"{commit}^", head=commit, repo_root=tree,
                                package_dir=tree / "tabulate")
        record = {"commit": commit, "changed": len(changed)}
        if not changed:
            return record
        units = {u.qualname: u for u in enumerate_units(tree / "tabulate", repo_root=tree)}
        lines, summary = executed_lines(tree)
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
    finally:
        git("worktree", "remove", "--force", str(tree), cwd=upstream)
        shutil.rmtree(tree, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    parser.add_argument("--since", default="2022-05-20")
    parser.add_argument("--until", default="268615a")
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    commits = git("log", "--no-merges", "--reverse", f"--since={args.since}", "--format=%h",
                  args.until, "--", "tabulate", cwd=upstream).split()
    records = []
    for commit in commits:
        try:
            rec = scan_commit(upstream, commit)
        except subprocess.TimeoutExpired:
            rec = {"commit": commit, "skipped": f"test suite exceeded {TIMEOUT_S}s"}
        except Exception as exc:  # a commit that cannot be measured is reported, not hidden
            rec = {"commit": commit, "skipped": f"{type(exc).__name__}: {exc}"[:200]}
        records.append(rec)
        print(json.dumps(rec), flush=True)

    measured = [r for r in records if "never" in r]
    with_changes = [r for r in measured if r["changed"]]
    changed_total = sum(r["changed"] for r in with_changes)
    never_total = sum(len(r["never"]) for r in with_changes)
    summary = {
        "upstream": "https://github.com/astanin/python-tabulate",
        "range": f"non-merge commits touching tabulate/ since {args.since}, up to {args.until}",
        "commits_in_range": len(commits),
        "commits_skipped": sum(1 for r in records if "skipped" in r),
        "commits_measured_with_changed_functions": len(with_changes),
        "commits_with_a_never_run_function": sum(1 for r in with_changes if r["never"]),
        "changed_functions": changed_total,
        "changed_functions_never_run": never_total,
        "records": records,
    }
    out = REPO / "bench" / "history.json"
    out.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\n{summary['commits_with_a_never_run_function']} of "
          f"{summary['commits_measured_with_changed_functions']} commits changed a function "
          f"their own test suite never ran; {never_total} of {changed_total} changed functions "
          f"never ran. Written to {out}")


if __name__ == "__main__":
    main()
