"""Command-line interface for witnessed."""

import argparse
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


def _cmd_scan(args: argparse.Namespace) -> None:  # noqa: ARG001
    print("not implemented")
    sys.exit(2)


def _cmd_gate(args: argparse.Namespace) -> None:  # noqa: ARG001
    print("not implemented")
    sys.exit(2)


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
    sub.add_parser("scan", help="Map changed lines to functions and re-run baselines.")
    sub.add_parser("gate", help="Validate a witness file.")
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
