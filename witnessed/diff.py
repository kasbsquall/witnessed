"""Map changed lines between two git refs to function units of the head tree."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .units import enumerate_units, units_from_source

Change = Literal["added", "modified"]

_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


@dataclass(frozen=True)
class ChangedUnit:
    qualname: str
    file: str          # relative to repo root, forward slashes
    change: Change


def _parse_diff_lines(diff_output: str) -> dict[str, set[int]]:
    """Parse ``git diff --unified=0`` output.

    Returns a mapping of *file path* (as it appears in the diff, relative to
    the repo root) → set of line numbers in the **head** version that were
    added, changed, or adjacent to a pure deletion.

    Only ``+`` lines that are not the ``+++`` header are counted; the file
    path comes from the ``+++ b/<path>`` header line.

    For deletion-only hunks (new-side count == 0) there are no ``+`` lines, so
    nothing would be recorded.  Instead we record the insertion point ``N``
    (clamped to at least 1) so that the function containing that line in head
    is detected as modified.
    """
    changed: dict[str, set[int]] = {}
    current_file: str | None = None
    current_line = 0  # next head line number to emit

    for raw in diff_output.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]  # strip "+++ b/"
            continue
        if raw.startswith("---"):
            continue
        if raw.startswith("@@"):
            m = _HUNK_RE.match(raw)
            if m:
                current_line = int(m.group(1))
                # Deletion-only hunk: new-side count is explicitly 0.
                # No '+' lines will follow, so record the insertion point now.
                new_count = int(m.group(2)) if m.group(2) is not None else 1
                if new_count == 0 and current_file is not None:
                    changed.setdefault(current_file, set()).add(max(1, current_line))
            continue
        if current_file is None:
            continue
        if raw.startswith("+"):
            changed.setdefault(current_file, set()).add(current_line)
            current_line += 1
        elif not raw.startswith("-"):
            # Context line (should not exist with --unified=0, but be safe).
            current_line += 1

    return changed


def _git_show_source(ref: str, rel_file: str, repo_root: Path) -> str | None:
    """Return the text of *rel_file* at git ref *ref*, or None if absent."""
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_file}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _package_paths(package_dir: Path, repo_root: Path) -> list[str]:
    """Return all .py files under *package_dir* as repo-root-relative posix paths."""
    repo_root = repo_root.resolve()
    package_dir = package_dir.resolve()
    return [
        py.relative_to(repo_root).as_posix()
        for py in sorted(package_dir.rglob("*.py"))
    ]


def changed_units(
    base: str,
    head: str,
    repo_root: Path,
    package_dir: Path,
) -> list[ChangedUnit]:
    """Return the list of functions in *head* that were added or modified relative to *base*.

    Steps:
    1. Run ``git diff --unified=0 <base> <head> -- <package paths>`` and parse
       hunk headers to learn which lines of *head* changed.
    2. Enumerate function units of *head* (from the working tree).
    3. For each head unit whose span overlaps the changed lines:
       - If the qualname does not appear in *base* → "added".
       - If it appears in *base* and any body line changed → "modified".
    4. Deleted functions (in base but not head) are ignored.
    """
    repo_root = repo_root.resolve()
    package_dir = package_dir.resolve()
    pkg_rel = package_dir.relative_to(repo_root).as_posix()

    # --- 1. Get changed lines in head ------------------------------------------
    pkg_paths = _package_paths(package_dir, repo_root)
    if not pkg_paths:
        return []

    diff_result = subprocess.run(
        ["git", "diff", "--unified=0", base, head, "--"] + pkg_paths,
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if diff_result.returncode != 0:
        raise RuntimeError(
            f"git diff failed (exit {diff_result.returncode}):\n{diff_result.stderr}"
        )

    changed_lines: dict[str, set[int]] = _parse_diff_lines(diff_result.stdout)
    if not changed_lines:
        return []

    # --- 2. Enumerate head units (from working tree) ----------------------------
    head_units = enumerate_units(package_dir, repo_root=repo_root)

    # --- 3. Build base qualname set (per file, lazily) --------------------------
    base_qualnames_by_file: dict[str, set[str]] = {}

    def _base_qualnames(rel_file: str) -> set[str]:
        if rel_file not in base_qualnames_by_file:
            src = _git_show_source(base, rel_file, repo_root)
            if src is None:
                base_qualnames_by_file[rel_file] = set()
            else:
                units = units_from_source(src, rel_file, pkg_rel)
                base_qualnames_by_file[rel_file] = {u.qualname for u in units}
        return base_qualnames_by_file[rel_file]

    # --- 4. Classify units -------------------------------------------------------
    results: list[ChangedUnit] = []
    for unit in head_units:
        file_changes = changed_lines.get(unit.file)
        if not file_changes:
            continue
        # The span is def_line..body_end (inclusive); a change anywhere in the
        # full span — including the def line itself for renames/signature changes
        # — counts as touching this unit.
        span = set(range(unit.def_line, unit.body_end + 1))
        if not span.intersection(file_changes):
            continue

        base_qns = _base_qualnames(unit.file)
        if unit.qualname not in base_qns:
            change: Change = "added"
        else:
            change = "modified"

        results.append(ChangedUnit(qualname=unit.qualname, file=unit.file, change=change))

    return results
