# Witnessed

Your agent says it tested the change. Witnessed shows which of the functions it touched nobody has ever seen running, and sends IBM Bob to find a witness for each one.

Work in progress for the IBM Bob 2.0 Hackathon (lablab.ai, September 25 to 27, 2026). The specification is in [docs/SPEC.md](docs/SPEC.md).

## The real case

Upstream python-tabulate commit [c327d6c](https://github.com/astanin/python-tabulate/commit/c327d6c) (Sergey Astanin, 2026-03-09, "implement support of JSONL and CSV input formats in command line utility") is the first commit of upstream PR #419. With the test suite of that commit, 2 of its 6 changed functions never ran anywhere: `_read_jsonl_file` and `_read_csv_file`. The other 4 ran only inside subprocesses started by `test/test_cli.py`. The maintainer added tests for the new options later in the same PR (upstream 791c4bf and 17bf1cf).

In the Witness mode, Bob spawned two parallel subagents and both witnesses passed the gate: 2 unwitnessed before, 0 after.

The branches are `hist/c327d6c-base` (tabulate at 164b367, the parent), `hist/c327d6c` (the upstream commit replayed unchanged, with its original author and message) and `hist/c327d6c-witnessed` (the two witnesses Bob wrote, on top).

## Reproduce in 60 seconds

```
pip install -e .
git checkout hist/c327d6c
witnessed scan --base hist/c327d6c-base --head hist/c327d6c
git restore --source=hist/c327d6c-witnessed witnesses
witnessed gate witnesses/tabulate._read_jsonl_file.py --target tabulate._read_jsonl_file
witnessed gate witnesses/tabulate._read_csv_file.py --target tabulate._read_csv_file
witnessed report
```

The scan prints "2 of 6 changed functions were never seen running", both gates print "accepted", and the report is written to `docs/report.html`.

## How Bob is used

The `Witness` custom mode (defined in `.bob/custom_modes.yaml`) can edit only `witnesses/*.py`. It loads the `witness-hunt` skill and spawns one parallel subagent per unwitnessed function. Bob also wrote the code of this repository during the hackathon. The task summary screenshots of every Bob session are in `bob_sessions/`.

## Evidence levels

| Level | Meaning |
|---|---|
| `used` | The function ran in at least one baseline marked `kind = "used"` (a real workload, not a test). |
| `tested` | The function ran only in baselines marked `kind = "tested"` (test suites). |
| `agent_witnessed` | The function was unwitnessed after the scan baselines, but an agent wrote a witness that passed all six gate rules. |
| `unwitnessed` | No evidence that anyone has run the function. |

## The six gate rules

A witness promotes a function to `agent_witnessed` only if all of the following hold:

1. Exit code 0 within 30 seconds.
2. Coverage shows executed lines inside the target body.
3. The SHA-256 of the target source file is unchanged after the run.
4. The witness calls the target through its package path.
5. The witness never assigns attributes of the target module.
6. The witness asserts on the value the target returns.

## What the gate does not prove

Rule 4 checks that the witness calls the target by name through the package path (e.g. `tabulate._is_file(...)` or `from tabulate import _is_file; _is_file(...)`). This resolves a name, not a binding. A witness can shadow the name, for example by assigning `_is_file = lambda x: True` before the call, and still satisfy rule 4 syntactically. The gate does not verify that the name was not rebound.

Rule 2 is the defence against this: coverage measures which source lines inside the real function body executed. If the name was rebound to a different callable the original body lines will not appear in the coverage report and the gate will reject with `body_not_executed`. The combination of rule 4 (name check) and rule 2 (body coverage) makes it substantially harder to fool the gate, but a witness that replaces the body with identical source could still pass. The gate is a heuristic.

## How it was validated

A function added and never called is reported as never seen running. Checking real history exposed two defects in Witnessed itself: deletion-only hunks were silently ignored (the containing function was not reported as modified), and subprocesses started by test suites were not measured. Both were fixed with regression tests.

## How it differs from diff-cover

diff-cover reports changed lines without coverage data for those lines. Witnessed works per function body, separates test runs from real-world use, and asks an agent for evidence that has to pass a six-rule gate. The result is a verdict for each function.

## Data and license

`sample/tabulate` is [python-tabulate](https://github.com/astanin/python-tabulate) (MIT) at commit 268615a on main, and at 164b367 plus c327d6c on the `hist/` branches.

This repository is MIT licensed. See [LICENSE](LICENSE).
