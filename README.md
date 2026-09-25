# Witnessed

Your agent says it tested the change. Witnessed shows which of the functions it touched nobody has ever seen running, and sends IBM Bob to find a witness for each one.

Work in progress for the IBM Bob 2.0 Hackathon (lablab.ai, September 25 to 27, 2026). The specification is in [docs/SPEC.md](docs/SPEC.md).

`sample/tabulate/` is [python-tabulate](https://github.com/astanin/python-tabulate) at commit 268615a, MIT licensed, vendored unchanged as the sample project.

## What the gate does not prove

Rule 4 checks that the witness calls the target **by name through the package path** (e.g. `tabulate._is_file(...)` or `from tabulate import _is_file; _is_file(...)`). This resolves a **name**, not a **binding**. A witness can shadow the name — for example by assigning `_is_file = lambda x: True` before the call — and still satisfy rule 4 syntactically. The gate does not verify that the name was not rebound.

Rule 2 is the defence against this: coverage measures which source lines inside the **real** function body executed. If the name was rebound to a different callable the original body lines will not appear in the coverage report and the gate will reject with `body_not_executed`. The combination of rule 4 (name check) and rule 2 (body coverage) makes it substantially harder to fool the gate, but a witness that replaces the body with identical source could still pass. The gate is a heuristic, not a proof.
