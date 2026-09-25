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
3. **No .py file under the package directory was modified during the run.**
   The gate snapshots every .py file in the package directory (SHA-256 plus
   mtime) before and after the run. If any file changed -- including sibling
   modules, not just the file that contains the target -- the witness is
   rejected. This also catches writes made through the shell, since the edit
   tool fileRegex only restricts the edit tool, not subprocess calls.
4. **The witness calls the target through its package path.** The call site must
   resolve to the real function via the package import system, not a local copy
   or alias.
5. **The witness never assigns attributes of the target module.** Monkey-patching
   or replacing names on the module object is forbidden.
6. **The witness asserts a comparison or isinstance/len check on the return value.**
   There must be at least one `assert` statement whose test is a comparison
   (==, !=, <, <=, >, >=, in, not in), an isinstance call, or a len-based
   comparison applied to the return value or something derived from it by
   subscript or attribute access. Bare truthiness (`assert result`) and identity
   against None (`assert result is None`, `assert result is not None`) do not
   count.

## Seven rejection reasons

| Reason | Meaning |
|---|---|
| `nonzero_exit` | The witness script exited with a non-zero status code. |
| `timeout` | The witness script did not finish within 30 seconds. |
| `body_not_executed` | No line inside the target's body was recorded as executed by coverage. |
| `target_modified` | At least one .py file in the package directory changed (SHA-256 or mtime) during the run. |
| `no_call_site` | The witness does not contain a call to the target through its package path. |
| `patches_target` | The witness assigns one or more attributes on the target's module. |
| `no_assertion` | The witness contains no substantive assertion (comparison, isinstance, or len check) on the value returned by the target. |
