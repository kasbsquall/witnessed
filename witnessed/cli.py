"""Command-line interface for witnessed."""

import argparse
import sys


def _cmd_baseline(args: argparse.Namespace) -> None:  # noqa: ARG001
    print("not implemented")
    sys.exit(2)


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
