"""Run every documented example from tabulate's own README, in order.

This is the "used" baseline: code the project's documentation tells people to
write. The examples are taken from sample/tabulate/README.md as they are, not
chosen by us, so nothing here was picked to make a function look used.
An example that raises is reported and skipped; it does not stop the others.
"""
from pathlib import Path
import sys

README = Path(__file__).resolve().parents[1] / "tabulate" / "README.md"
sys.path.insert(0, str(README.parent))


def examples(text):
    block = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">>> "):
            if block:
                yield "\n".join(block)
            block = [stripped[4:]]
        elif stripped.startswith("... ") and block:
            block.append(stripped[4:])
        elif stripped == "..." and block:
            block.append("")
    if block:
        yield "\n".join(block)


def main():
    # Box-drawing formats print characters a Windows console codepage cannot encode.
    sys.stdout.reconfigure(encoding="utf-8")
    scope = {}
    ran = failed = 0
    for source in examples(README.read_text(encoding="utf-8")):
        try:
            exec(compile(source, "README.md", "exec"), scope)
            ran += 1
        except Exception as exc:
            failed += 1
            print(f"example failed: {type(exc).__name__}: {source.splitlines()[0][:70]}", file=sys.stderr)
    print(f"readme examples: {ran} ran, {failed} failed")


if __name__ == "__main__":
    main()
