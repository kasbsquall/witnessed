# Gate Rules and Rejection Reasons

Source: docs/SPEC.md §4.

## Six gate rules

A witness promotes a function to `agent_witnessed` only if **all** of the
following hold:

1. **Exit code 0 within 30 seconds.** The witness script must complete
   successfully and within the time limit.
2. **Coverage shows executed lines inside the target's body.** At least one
   line between `node.body[0].lineno` and `node.end_lineno` (inclusive) must
   appear as executed in the coverage report. The `def` line does not count.
3. **The SHA-256 of the target's file is unchanged after the run.** The witness
   must not write to, truncate, or otherwise modify the source file that
   contains the target.
4. **The witness calls the target through its package path.** The call site must
   resolve to the real function via the package import system, not a local copy
   or alias.
5. **The witness never assigns attributes of the target module.** Monkey-patching
   or replacing names on the module object is forbidden.
6. **The witness asserts on the value the target returns.** There must be at
   least one `assert` statement (or equivalent) that checks the return value.

## Seven rejection reasons

| Reason | Meaning |
|---|---|
| `nonzero_exit` | The witness script exited with a non-zero status code. |
| `timeout` | The witness script did not finish within 30 seconds. |
| `body_not_executed` | No line inside the target's body was recorded as executed by coverage. |
| `target_modified` | The SHA-256 of the target's source file changed during the run. |
| `no_call_site` | The witness does not contain a call to the target through its package path. |
| `patches_target` | The witness assigns one or more attributes on the target's module. |
| `no_assertion` | The witness contains no assertion on the value returned by the target. |
