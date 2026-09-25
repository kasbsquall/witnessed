# Witnessed: specification

## 1. What it is

Your agent says it tested the change. Witnessed shows which of the functions it touched nobody has ever seen running, and sends Bob to find a witness for each one.

Workflow improved: code review of changes written by an AI agent. A reviewer reads "added tests, all passing" and approves, with no quick way to know which parts of the change ever executed. Global coverage does not help, because a function counts as covered as soon as its module is imported.

## 2. Evidence levels

A function is observed only when a line of its **body** executed: from `node.body[0].lineno` to `node.end_lineno`. The `def` line runs at import time and never counts.

| Level | Meaning | Strength |
|---|---|---|
| `used` | Seen running by the real-use baseline (documented examples of the sample project) | 3 |
| `tested` | Seen running only by the test suite | 2 |
| `agent_witnessed` | Seen running only by an agent-written witness that passed the gate | 1 |
| `unwitnessed` | Never seen running | 0 |

A function seen by several baselines keeps the strongest level. A verdict over several functions takes the weakest.

Measured on the vendored sample (tabulate at 268615a, 76 functions): 68 used, 8 tested only, 0 unwitnessed.

## 3. Flow

1. `witnessed baseline` runs each baseline under coverage.py and writes `.witnessed/baseline.json`.
2. `witnessed scan --base <ref> --head <ref>` maps changed lines to functions of `head` (added or modified), re-runs the baselines on `head`, and writes `.witnessed/scan.json` and `.witnessed/comment.md`.
3. In Bob IDE, the `witness` mode reads `scan.json` and spawns one `general` subagent per unwitnessed function, in parallel. Each follows the `witness-hunt` skill, writes `witnesses/<qualname>.py` and runs `witnessed gate`.
4. `witnessed report` writes `docs/report.html`, published on GitHub Pages.
5. `claim.md` holds the verbatim final message of the agent that wrote the change. The report shows it next to what actually ran.
6. Optional CI path: `bob run --mode witness --max-cost <n> --format json` per unwitnessed function.

## 4. The gate

A witness promotes a function to `agent_witnessed` only if all of these hold:

1. Exit code 0 within 30 seconds.
2. Coverage shows executed lines inside the target's body.
3. The SHA-256 of the target's file is unchanged after the run.
4. The witness calls the target through its package path.
5. The witness never assigns attributes of the target module.
6. The witness asserts on the value the target returns.

Rejection reasons: `nonzero_exit`, `timeout`, `body_not_executed`, `target_modified`, `no_call_site`, `patches_target`, `no_assertion`.

What it does not prove: rule 4 resolves a name, not a binding. Rule 2 still measures that the real body ran.

## 5. Bob is the product

- `.bob/custom_modes.yaml`: mode `witness` with `read`, `execute`, `skill`, `subagent`, and `edit` limited by `fileRegex: "^witnesses/.*\.py$"`. While hunting for evidence, Bob cannot edit product code.
- `.bob/skills/witness-hunt/`: the recipe each subagent follows, plus the gate rules.
- Parallel `general` subagents, one per unwitnessed function.

## 6. Layout

```
witnessed/        units.py observe.py diff.py verdict.py gate.py report.py cli.py
tests/            pytest, including adversarial gate tests
sample/tabulate/  python-tabulate at 268615a, MIT, with its LICENSE
sample/usage/     documented tabulate examples (the real-use baseline)
witnesses/        witnesses written by subagents
.bob/             custom_modes.yaml, skills/witness-hunt/
docs/             SPEC.md, report.html
bob_sessions/     task session summary screenshots
claim.md          the audited agent's final message, verbatim
```

Standard library plus coverage and pytest. Must run on Windows and Linux.

## 7. Claims

Every number shown anywhere comes from a file in `.witnessed/` or `bench/`. Every percentage carries its denominator.
