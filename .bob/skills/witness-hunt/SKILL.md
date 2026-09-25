---
name: witness-hunt
description: Write and verify a witness for one function nobody has seen running.
---

# Witness Hunt

Follow these steps exactly. Never edit any file outside `witnesses/`.

## 1. Read the target

Read only the target function's body (the lines given in the body range) and
any imports or helpers it needs to run. Do not read unrelated modules.

## 2. Write the witness

Create `witnesses/<qualname>.py` (replacing dots in the qualname with slashes
only for the directory portion — the file name is `<qualname>.py` with the full
dotted name). The witness must:

- Import the target through its package path (e.g. `from tabulate import tabulate`).
- Call the target with realistic, non-trivial input.
- Assert on the value the target returns.
- Be the smallest script that satisfies the six gate rules in `gate-rules.md`.

## 3. Run the gate

```
python -m witnessed.cli gate witnesses/<qualname>.py --target <qualname>
```

## 4. Handle rejection (at most once)

If the gate rejects the witness, read the rejection reason from the output,
consult `gate-rules.md` to understand it, fix the witness accordingly, and run
the gate again. Do not attempt a third run.

## 5. Report

Report exactly one of:

- `ACCEPTED — <qualname>` with a one-line description of what was asserted.
- `REJECTED — <qualname>: <reason>` with a one-line explanation of what the
  gate found.
