# IBM Bob sessions

The code in `witnessed/`, `tests/` and `.bob/` was written by IBM Bob in tasks 1 to 12, run on September 25, 2026. Task 13 is the witness hunt recorded live for the demo video. Each screenshot is the task summary as Bob showed it at the end. Costs are the task costs recorded by Bob, in Bobcoins.

| # | Task | Mode | Bobcoins | Screenshot |
|---|---|---|---:|---|
| 1 | Package skeleton and function units | Agent | 0.417 | [task01](nightshift_task01_package_units_summary.png) |
| 2 | Baselines under coverage, and three fixes to task 1 | Agent | 5.456 | [task02](nightshift_task02_baselines_summary.png) |
| 3 | Scan a change, and one fix to task 2 | Agent | 1.374 | [task03](nightshift_task03_scan_summary.png) |
| 4 | The witness gate, and one fix to task 3 | Agent | 4.750 | [task04](nightshift_task04_gate_summary.png) |
| 5 | The Witness custom mode and the witness-hunt skill | Agent | 0.523 | [task05](nightshift_task05_witness_mode_skill_summary.png) |
| 6 | A change under audit: typst output for tabulate | Agent | 3.203 | [task06](nightshift_task06_typst_change_summary.png) |
| 7 | Two defects found on real history: deletion-only hunks, subprocesses | Agent | 8.485 | [task07](nightshift_task07_history_defects_summary.png) |
| 8 | Witness hunt on upstream c327d6c, two parallel subagents | Witness | 0.653 | [summary](nightshift_task08_witness_hunt_summary.png), [subagents](nightshift_task08_witness_hunt_parallel_subagents.png) |
| 9 | Report command, quieter scan, README | Agent | 3.228 | [task09](nightshift_task09_report_readme_summary.png) |
| 10 | Report visual design and three render fixes | Agent | 1.929 | [task10](nightshift_task10_report_design_summary.png) |
| 11 | Report: before and after, one color per meaning, upstream commit, witness code and gate rules | Agent | 0.720 | [task11](nightshift_task11_report_before_after_summary.png) |
| 12 | Gate hardening: hash every package file, reject trivial assertions | Agent | 2.965 | [task12](nightshift_task12_gate_hardening_summary.png) |
| 13 | Witness hunt on upstream c327d6c, recorded live: two parallel subagents; the gate rejected their first witnesses (nonzero_exit) and they fixed them | Witness | 1.601 | [task13](nightshift_task13_live_witness_hunt_summary.png) |

Total: 35.304 Bobcoins of the 40 available. Each task cost already includes the subagents it started: Bob lists them as child tasks too (0.114 and 0.114 in task 8, 0.809 and 0.683 in task 13), so they are not added again. The witnesses and the report on the `hist/c327d6c-witnessed` branch come from task 13; the task 8 witnesses are kept on `hist/c327d6c-witnessed-task08`.

## Changes made after the Bob sessions

After the second review round, Claude (Anthropic) changed code that Bob had written. None of it was done in Bob, and no Bobcoins were spent on it.

- Gate, rule 2: `scan.json` did not carry the body range of each function, so the gate skipped rule 2 without saying so, and a witness that shadowed the target name was accepted. The scan now records the range and the gate rejects any witness when the range is unknown (`witnessed/cli.py`, `witnessed/gate.py`).
- Gate, rule 6: tautologies, a result name rebound before the assert, and asserts that never execute are now rejected.
- Five regression tests for those cases at the end of `tests/test_gate.py`.
- Report: new layout and copy (`witnessed/report.py`, `witnessed/report_css.py`, `witnessed/_icons.py` with Phosphor Light icons, MIT), including the section on how Bob closed the gap, which reads `witness_hunt.json`, and the history section, which reads `bench/history.json`.
- `pyproject.toml`: the build backend was wrong and `pip install -e .` failed; pytest is now a dependency because the tested baseline needs it.

