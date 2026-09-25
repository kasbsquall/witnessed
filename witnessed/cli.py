"""Command-line interface for witnessed."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path


def _cmd_baseline(args: argparse.Namespace) -> None:  # noqa: ARG001
    from .observe import run_baselines, write_baseline_json

    repo_root = Path.cwd()
    package_dir = Path("sample/tabulate/tabulate")

    payload = run_baselines(repo_root, package_dir)
    out_path = write_baseline_json(repo_root, payload)

    counts: Counter[str] = Counter()
    for info in payload["units"].values():
        counts[info["level"]] += 1

    print(f"baseline.json written to {out_path}")
    for level in ("used", "tested", "agent_witnessed", "unwitnessed"):
        if counts[level]:
            print(f"  {level}: {counts[level]}")

    # Report any non-zero exits.
    for rec in payload["baselines"]:
        if rec["exit_code"] != 0:
            print(
                f"  baseline '{rec['id']}' exited {rec['exit_code']}",
                file=sys.stderr,
            )


def _resolve_ref(ref: str, repo_root: Path) -> str:
    """Return the full SHA for *ref*, or exit 2 on failure."""
    result = subprocess.run(
        ["git", "rev-parse", ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"error: could not resolve git ref {ref!r}", file=sys.stderr)
        sys.exit(2)
    return result.stdout.strip()


def _cmd_scan(args: argparse.Namespace) -> None:
    from .diff import changed_units
    from .observe import load_baselines, run_baselines
    from .verdict import Level, level_label, pr_verdict

    repo_root = Path.cwd()
    # TODO: make package_dir configurable; default to the tabulate sample.
    package_dir = Path("sample/tabulate/tabulate")

    base_ref: str = args.base
    head_ref: str = getattr(args, "head", None) or "HEAD"

    # Resolve both refs to full SHAs.
    base_sha = _resolve_ref(base_ref, repo_root)
    head_sha = _resolve_ref(head_ref, repo_root)

    # Verify that the working tree HEAD matches the requested head ref.
    actual_head = _resolve_ref("HEAD", repo_root)
    if actual_head != head_sha:
        print(
            f"error: HEAD ({actual_head[:12]}) does not match --head {head_ref!r} "
            f"({head_sha[:12]}). Check out the head commit before running scan.",
            file=sys.stderr,
        )
        sys.exit(2)

    # 1. Map changed lines to function units.
    changed = changed_units(
        base=base_sha,
        head=head_sha,
        repo_root=repo_root,
        package_dir=package_dir,
    )

    # 2. Run baselines on the current working tree to get evidence levels.
    payload = run_baselines(repo_root=repo_root, package_dir=package_dir)
    units_info: dict[str, dict] = payload["units"]

    # 3. Build the changed list with levels.
    changed_records = []
    for cu in changed:
        info = units_info.get(cu.qualname, {})
        level: Level = info.get("level", "unwitnessed")  # type: ignore[assignment]
        seen_by: list[str] = info.get("seen_by", [])
        changed_records.append(
            {
                "qualname": cu.qualname,
                "file": cu.file,
                "change": cu.change,
                "level": level,
                "seen_by": seen_by,
            }
        )

    # 4. Counts.
    counts: Counter[str] = Counter()
    for rec in changed_records:
        counts[rec["level"]] += 1
    total = len(changed_records)
    unwitnessed = counts["unwitnessed"]

    scan_payload = {
        "base": base_sha,
        "head": head_sha,
        "changed": changed_records,
        "counts": {
            "used": counts["used"],
            "tested": counts["tested"],
            "agent_witnessed": counts["agent_witnessed"],
            "unwitnessed": counts["unwitnessed"],
        },
    }

    # 5. Write .witnessed/scan.json.
    witnessed_dir = repo_root / ".witnessed"
    witnessed_dir.mkdir(exist_ok=True)
    scan_path = witnessed_dir / "scan.json"
    scan_path.write_text(json.dumps(scan_payload, indent=2), encoding="utf-8")

    # 6. Build and write .witnessed/comment.md.
    comment_lines: list[str] = []
    comment_lines.append(
        f"{unwitnessed} of {total} changed functions were never seen running."
    )

    if changed_records:
        comment_lines.append("")
        comment_lines.append("| function | change | level | seen by |")
        comment_lines.append("| --- | --- | --- | --- |")
        for rec in changed_records:
            fn = rec["qualname"]
            change = rec["change"]
            lv: Level = rec["level"]  # type: ignore[assignment]
            label = level_label(lv)
            seen = ", ".join(rec["seen_by"]) if rec["seen_by"] else "-"
            comment_lines.append(f"| {fn} | {change} | {label} | {seen} |")

    comment_path = witnessed_dir / "comment.md"
    comment_path.write_text("\n".join(comment_lines) + "\n", encoding="utf-8")

    # 7. Determine and print verdict.
    levels: list[Level] = [rec["level"] for rec in changed_records]  # type: ignore[misc]
    verdict = pr_verdict(levels)
    verdict_label = level_label(verdict)

    print(f"scan.json written to {scan_path}")
    print(f"comment.md written to {comment_path}")
    print(f"verdict: {verdict} — {verdict_label}")


def _cmd_gate(args: argparse.Namespace) -> None:
    from .gate import run_gate

    repo_root = Path.cwd()
    witness_path = Path(args.witness)
    qualname: str = args.target

    if not witness_path.exists():
        print(f"error: witness file not found: {witness_path}", file=sys.stderr)
        sys.exit(2)

    verdict = run_gate(
        witness_path=witness_path,
        qualname=qualname,
        repo_root=repo_root,
    )

    status = "accepted" if verdict["accepted"] else f"rejected ({verdict['reason']})"
    print(f"gate: {status}")
    if verdict["body_lines_executed"]:
        print(f"  body lines executed: {verdict['body_lines_executed']}")

    gate_dir = repo_root / ".witnessed" / "gate"
    safe_name = qualname.replace(".", "_")
    verdict_path = gate_dir / f"{safe_name}.json"
    print(f"  verdict written to {verdict_path}")

    if not verdict["accepted"]:
        sys.exit(1)


def _cmd_report(args: argparse.Namespace) -> None:  # noqa: ARG001
    print("not implemented")
    sys.exit(2)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="witnessed",
        description="Track which functions were actually witnessed running.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("baseline", help="Run baselines and record coverage.")

    scan_parser = sub.add_parser(
        "scan", help="Map changed lines to functions and re-run baselines."
    )
    scan_parser.add_argument(
        "--base", required=True, metavar="REF", help="Base git ref (e.g. main, SHA)."
    )
    scan_parser.add_argument(
        "--head",
        default=None,
        metavar="REF",
        help="Head git ref (default: HEAD).",
    )

    gate_parser = sub.add_parser("gate", help="Validate a witness file.")
    gate_parser.add_argument("witness", metavar="WITNESS", help="Path to the witness .py file.")
    gate_parser.add_argument(
        "--target",
        required=True,
        metavar="QUALNAME",
        help="Fully-qualified function name, e.g. tabulate._is_file.",
    )
    sub.add_parser("report", help="Generate HTML report.")

    args = parser.parse_args()

    dispatch = {
        "baseline": _cmd_baseline,
        "scan": _cmd_scan,
        "gate": _cmd_gate,
        "report": _cmd_report,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()
