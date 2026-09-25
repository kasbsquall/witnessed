"""Use tabulate's command line the way its README documents it.

Calls the CLI entry point in-process so coverage sees it, feeding a small
table through stdin in a few of the documented output formats.
"""
from pathlib import Path
import io
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tabulate"))

from tabulate import cli  # noqa: E402

DATA = "name age city\nAlice 24 Lima\nBob 19 Cusco\n"
RUNS = [
    ["-1"],
    ["-1", "-f", "grid"],
    ["-1", "-f", "github"],
    ["-1", "-f", "pipe", "-F", ".2f"],
    ["-f", "plain", "-s", " "],
]


def main():
    for args in RUNS:
        sys.stdin = io.StringIO(DATA)
        # The CLI closes stdout when it finishes, so each run gets its own.
        sys.stdout = io.StringIO()
        sys.argv = ["tabulate", *args]
        try:
            cli._main()
        except SystemExit as exc:
            if exc.code not in (0, None):
                print(f"cli exited {exc.code} for {args}", file=sys.stderr)
    sys.stdin, sys.stdout = sys.__stdin__, sys.__stdout__
    print(f"cli examples: {len(RUNS)} runs")


if __name__ == "__main__":
    main()
