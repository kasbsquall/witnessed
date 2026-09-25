"""Tests for witnessed.diff (changed_units) and the scan subcommand end-to-end."""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from witnessed.diff import changed_units, _parse_diff_lines
from witnessed.verdict import level_label, pr_verdict


# ---------------------------------------------------------------------------
# Unit tests for _parse_diff_lines
# ---------------------------------------------------------------------------


def test_parse_diff_lines_added_hunk() -> None:
    """A single hunk adding two lines should produce those head line numbers."""
    diff = textwrap.dedent("""\
        diff --git a/pkg/mod.py b/pkg/mod.py
        --- a/pkg/mod.py
        +++ b/pkg/mod.py
        @@ -5,0 +6,2 @@
        +def foo():
        +    return 1
    """)
    result = _parse_diff_lines(diff)
    assert result == {"pkg/mod.py": {6, 7}}


def test_parse_diff_lines_multiple_files() -> None:
    """Lines from distinct files must be kept separate."""
    diff = textwrap.dedent("""\
        diff --git a/a.py b/a.py
        --- a/a.py
        +++ b/a.py
        @@ -1,0 +2,1 @@
        +x = 1
        diff --git a/b.py b/b.py
        --- a/b.py
        +++ b/b.py
        @@ -3,0 +4,1 @@
        +y = 2
    """)
    result = _parse_diff_lines(diff)
    assert result == {"a.py": {2}, "b.py": {4}}


def test_parse_diff_lines_deletion_only_hunk() -> None:
    """A deletion-only hunk (+N,0) must record the insertion point so the
    containing function is detected as modified (regression for bug where
    deletion-only hunks produced an empty changed-lines set)."""
    diff = textwrap.dedent("""\
        diff --git a/pkg/mod.py b/pkg/mod.py
        --- a/pkg/mod.py
        +++ b/pkg/mod.py
        @@ -1661 +1660,0 @@ def _wrap_text_to_colwidths(
        -                    if line.strip() != ""
    """)
    result = _parse_diff_lines(diff)
    # The insertion point is 1660; it must be recorded so the enclosing
    # function is detected as modified.
    assert result == {"pkg/mod.py": {1660}}


# ---------------------------------------------------------------------------
# Helpers for git-repo tests
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout. Raises on non-zero exit."""
    result = subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed:\n{result.stderr}"
        )
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    """Initialise a bare git repo in *tmp_path* with user config."""
    _git(["init", "-b", "main"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test"], tmp_path)
    return tmp_path


def _commit_all(repo: Path, message: str) -> str:
    """Stage everything and commit; return the new SHA."""
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)
    return _git(["rev-parse", "HEAD"], repo)


# ---------------------------------------------------------------------------
# Full end-to-end: changed_units on a two-commit repo
# ---------------------------------------------------------------------------


def _setup_two_commit_repo(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """Create a repo where:
      - base commit: empty package (just __init__.py with no functions)
      - head commit: adds two functions, alpha and beta

    Returns (repo_root, package_dir, base_sha, head_sha).
    """
    repo = _make_repo(tmp_path)

    # --- base commit: empty package ---
    pkg = repo / "mypkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("# empty\n")
    base_sha = _commit_all(repo, "base: empty package")

    # --- head commit: add two functions ---
    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def alpha():
                return "alpha"

            def beta():
                return "beta"
        """)
    )
    head_sha = _commit_all(repo, "head: add alpha and beta")

    return repo, pkg, base_sha, head_sha


def test_changed_units_both_added(tmp_path: Path) -> None:
    """Both alpha and beta must appear as 'added' changed units."""
    repo, pkg, base_sha, head_sha = _setup_two_commit_repo(tmp_path)
    result = changed_units(base_sha, head_sha, repo_root=repo, package_dir=pkg)
    qualnames = {cu.qualname: cu.change for cu in result}
    assert "mypkg.alpha" in qualnames
    assert "mypkg.beta" in qualnames
    assert qualnames["mypkg.alpha"] == "added"
    assert qualnames["mypkg.beta"] == "added"


def test_changed_units_modified(tmp_path: Path) -> None:
    """A function that existed in base and has a changed body line is 'modified'."""
    repo = _make_repo(tmp_path)
    pkg = repo / "mypkg"
    pkg.mkdir()

    # base: one function
    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def greet():
                return "hello"
        """)
    )
    base_sha = _commit_all(repo, "base")

    # head: modify the body
    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def greet():
                return "world"
        """)
    )
    head_sha = _commit_all(repo, "head")

    result = changed_units(base_sha, head_sha, repo_root=repo, package_dir=pkg)
    assert len(result) == 1
    assert result[0].qualname == "mypkg.greet"
    assert result[0].change == "modified"


def test_changed_units_deleted_ignored(tmp_path: Path) -> None:
    """A function deleted in head must not appear in changed_units."""
    repo = _make_repo(tmp_path)
    pkg = repo / "mypkg"
    pkg.mkdir()

    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def keep():
                return 1

            def remove():
                return 2
        """)
    )
    base_sha = _commit_all(repo, "base")

    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def keep():
                return 1
        """)
    )
    head_sha = _commit_all(repo, "head: remove 'remove'")

    result = changed_units(base_sha, head_sha, repo_root=repo, package_dir=pkg)
    qualnames = [cu.qualname for cu in result]
    assert "mypkg.remove" not in qualnames


def test_changed_units_modified_subdirectory(tmp_path: Path) -> None:
    """Regression: a package inside a subdirectory must report modified, not added.

    Previously _enumerate_units_from_source built the qualname from the full
    package path ("sample.tabulate.tabulate._is_file") while enumerate_units
    produced "tabulate._is_file", so 0 of N qualnames matched and every
    modified function was reported as "added".

    Layout: repo/sub/mypkg/mod.py (package sits two directories deep).
    """
    repo = _make_repo(tmp_path)

    sub = repo / "sub"
    sub.mkdir()
    pkg = sub / "mypkg"
    pkg.mkdir()

    # base commit: function exists with its original body
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        textwrap.dedent("""\
            def compute():
                return 1
        """)
    )
    base_sha = _commit_all(repo, "base")

    # head commit: same function, body changed
    (pkg / "mod.py").write_text(
        textwrap.dedent("""\
            def compute():
                return 2
        """)
    )
    head_sha = _commit_all(repo, "head: modify compute body")

    result = changed_units(base_sha, head_sha, repo_root=repo, package_dir=pkg)
    assert len(result) == 1, f"expected 1 result, got {result}"
    cu = result[0]
    assert cu.qualname == "mypkg.mod.compute", f"wrong qualname: {cu.qualname!r}"
    assert cu.change == "modified", (
        f"expected 'modified' but got {cu.change!r} — "
        "qualname mismatch between head and base enumeration"
    )



# ---------------------------------------------------------------------------
# Scan end-to-end: 1 of 2 changed functions never seen running
# ---------------------------------------------------------------------------


def _setup_scan_repo(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """Build a repo suitable for the scan integration test.

    Layout:
      mypkg/__init__.py   — two functions: alpha (exercised), beta (not)
      witnessed.toml       — a 'tested' baseline that calls only alpha
      test_suite.py        — pytest that calls alpha only

    Commits:
      base  — empty package
      head  — adds alpha and beta
    """
    repo = _make_repo(tmp_path)

    pkg = repo / "mypkg"
    pkg.mkdir()

    # --- base commit ---
    (pkg / "__init__.py").write_text("# empty\n")
    base_sha = _commit_all(repo, "base: empty package")

    # --- head commit: add alpha + beta, test suite, toml ---
    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def alpha():
                return "alpha"

            def beta():
                return "beta"
        """)
    )

    # Test suite that only calls alpha.
    test_file = repo / "test_suite.py"
    test_file.write_text(
        textwrap.dedent(f"""\
            import sys, pathlib
            sys.path.insert(0, str(pathlib.Path(__file__).parent))
            from mypkg import alpha

            def test_alpha():
                assert alpha() == "alpha"
        """)
    )

    # witnessed.toml for this repo.
    pkg_posix = pkg.relative_to(repo).as_posix()
    test_posix = test_file.relative_to(repo).as_posix()
    (repo / "witnessed.toml").write_text(
        textwrap.dedent(f"""\
            [[baselines]]
            id = "tested"
            kind = "tested"
            commands = [
                ["-m", "pytest", "{test_posix}", "-p", "no:cacheprovider", "-q"],
            ]
        """)
    )

    head_sha = _commit_all(repo, "head: add alpha and beta")

    return repo, pkg, base_sha, head_sha


def test_scan_one_of_two_unwitnessed(tmp_path: Path) -> None:
    """scan: 1 of 2 changed functions (beta) must be unwitnessed; alpha tested."""
    from witnessed.diff import changed_units
    from witnessed.observe import run_baselines
    from witnessed.verdict import pr_verdict

    repo, pkg, base_sha, head_sha = _setup_scan_repo(tmp_path)

    # 1. Find changed units (both added).
    changed = changed_units(base_sha, head_sha, repo_root=repo, package_dir=pkg)
    qualnames_changed = {cu.qualname for cu in changed}
    assert "mypkg.alpha" in qualnames_changed, f"alpha missing from {qualnames_changed}"
    assert "mypkg.beta" in qualnames_changed, f"beta missing from {qualnames_changed}"

    # 2. Run baselines in the temporary repo.
    payload = run_baselines(repo_root=repo, package_dir=pkg)
    units_info = payload["units"]

    # 3. Assign levels to changed units.
    records = []
    for cu in changed:
        info = units_info.get(cu.qualname, {})
        level = info.get("level", "unwitnessed")
        seen_by = info.get("seen_by", [])
        records.append({"qualname": cu.qualname, "change": cu.change,
                        "level": level, "seen_by": seen_by})

    levels_map = {r["qualname"]: r["level"] for r in records}
    assert levels_map.get("mypkg.alpha") == "tested", \
        f"alpha level was {levels_map.get('mypkg.alpha')!r}"
    assert levels_map.get("mypkg.beta") == "unwitnessed", \
        f"beta level was {levels_map.get('mypkg.beta')!r}"

    # 4. Check counts.
    unwitnessed = sum(1 for r in records if r["level"] == "unwitnessed")
    total = len(records)
    assert unwitnessed == 1, f"expected 1 unwitnessed, got {unwitnessed}"
    assert total == 2, f"expected 2 total, got {total}"

    # 5. Write comment.md and verify its first line and table.
    from witnessed.verdict import level_label
    witnessed_dir = repo / ".witnessed"
    witnessed_dir.mkdir(exist_ok=True)

    comment_lines = [f"{unwitnessed} of {total} changed functions were never seen running."]
    comment_lines.append("")
    comment_lines.append("| function | change | level | seen by |")
    comment_lines.append("| --- | --- | --- | --- |")
    for rec in records:
        fn = rec["qualname"]
        change = rec["change"]
        label = level_label(rec["level"])
        seen = ", ".join(rec["seen_by"]) if rec["seen_by"] else "-"
        comment_lines.append(f"| {fn} | {change} | {label} | {seen} |")

    comment_text = "\n".join(comment_lines) + "\n"
    comment_path = witnessed_dir / "comment.md"
    comment_path.write_text(comment_text, encoding="utf-8")

    # Verify first line.
    first_line = comment_text.splitlines()[0]
    assert first_line == "1 of 2 changed functions were never seen running.", \
        f"unexpected first line: {first_line!r}"

    # Verify table contains both functions.
    assert "mypkg.alpha" in comment_text
    assert "mypkg.beta" in comment_text
    assert "never seen running" in comment_text
    assert "only by tests" in comment_text

    # 6. Verdict is the weakest = unwitnessed.
    verdict = pr_verdict([r["level"] for r in records])
    assert verdict == "unwitnessed"

    # Expose the generated comment for inspection.
    print("\n--- generated comment.md ---")
    print(comment_text)
    print("--- end ---")


# ---------------------------------------------------------------------------
# Regression: deletion-only hunk must surface the containing function
# ---------------------------------------------------------------------------


def test_changed_units_deletion_only_hunk(tmp_path: Path) -> None:
    """A commit that only deletes a line inside a function must report that
    function as 'modified' (regression: deletion-only hunks were silently
    ignored because no '+' lines were emitted)."""
    repo = _make_repo(tmp_path)
    pkg = repo / "mypkg"
    pkg.mkdir()

    # base: function with a filtering guard on line 4
    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def process(items):
                result = []
                for item in items:
                    if item.strip() != "":
                        result.append(item)
                return result
        """)
    )
    base_sha = _commit_all(repo, "base")

    # head: remove the filtering guard (pure deletion, no additions)
    (pkg / "__init__.py").write_text(
        textwrap.dedent("""\
            def process(items):
                result = []
                for item in items:
                    result.append(item)
                return result
        """)
    )
    head_sha = _commit_all(repo, "head: remove blank-line filter")

    result = changed_units(base_sha, head_sha, repo_root=repo, package_dir=pkg)
    qualnames = [cu.qualname for cu in result]
    assert "mypkg.process" in qualnames, (
        f"deletion-only hunk did not surface mypkg.process; got {qualnames}"
    )
    assert result[0].change == "modified"
