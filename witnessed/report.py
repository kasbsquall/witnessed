"""Generate docs/report.html from .witnessed/scan.json and gate verdicts.

Optional inputs, shown only when present: bob_sessions/witness_hunt.json (the
Bob session that wrote the witnesses) and bench/history.json (the history bench).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ._icons import icon
from .report_css import REPORT_CSS

# Level display config: (label, fill_color, outline_only)
_LEVEL_STYLE: dict[str, tuple[str, str, bool]] = {
    "used":            ("used in real runs",              "#CFC9BC", False),
    "tested":          ("only by tests",                  "#8A7A55", False),
    "agent_witnessed": ("never ran, now witnessed by Bob","#F2B544", True),
    "unwitnessed":     ("never seen running",             "#E0765A", True),
}
_LEVEL_ORDER = ["used", "tested", "agent_witnessed", "unwitnessed"]
_COMMIT_PREVIEW_LINES = 12
# Plain names for the baseline ids defined in witnessed.toml.
_BASELINE_NAMES = {
    "tested": "the project's own test suite, subprocesses included (baseline: tested)",
    "used": "the documented usage scripts (baseline: used)",
}
# Cells show the story first: what Bob witnessed, then what is still dark.
_CELL_ORDER = {"agent_witnessed": 0, "unwitnessed": 1, "used": 2, "tested": 3}

# Six gate rules in the order the gate evaluates them.
# Rule 1 covers both nonzero_exit and timeout (SPEC.md section 4).
_GATE_RULES: list[tuple[str, str]] = [
    ("nonzero_exit",      "exits with code 0 within 30 seconds"),
    ("body_not_executed", "executes the function body"),
    ("target_modified",   "does not modify any file in the package directory"),
    ("no_call_site",      "contains a call to the target"),
    ("patches_target",    "does not patch the target module"),
    ("no_assertion",      "asserts a comparison or isinstance/len check on the return value, and the assert runs"),
]


def _head_commit_message(head_sha: str, repo_root: Path) -> str:
    """Return the commit message for *head_sha*, or an empty string on failure."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%B", head_sha],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def _parse_git_trailers(commit_message: str) -> dict[str, str]:
    """Return a dict of trailer key -> value parsed from the end of *commit_message*."""
    trailers: dict[str, str] = {}
    if not commit_message:
        return trailers
    for line in reversed(commit_message.splitlines()):
        line = line.strip()
        if not line:
            continue
        if ": " in line:
            key, _, value = line.partition(": ")
            if all(c.isalnum() or c == "-" for c in key):
                trailers[key] = value.strip()
            else:
                break
        else:
            break
    return trailers


def _strip_trailers(commit_message: str, trailers: dict[str, str]) -> str:
    """Return *commit_message* without its trailer block (shown elsewhere)."""
    if not trailers:
        return commit_message
    lines = commit_message.rstrip().splitlines()
    while lines and (not lines[-1].strip() or lines[-1].partition(": ")[0].strip() in trailers):
        lines.pop()
    return "\n".join(lines)


def _remote_url(repo_root: Path) -> str:
    """Return the https remote URL for origin, or empty string."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if url.startswith("git@"):
                url = url.replace(":", "/", 1).replace("git@", "https://", 1)
            if url.endswith(".git"):
                url = url[:-4]
            return url
    except Exception:
        pass
    return ""


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_gate_verdicts(gate_dir: Path) -> dict[str, dict]:
    """Return a mapping qualname -> verdict dict for every .json in gate_dir."""
    verdicts: dict[str, dict] = {}
    if not gate_dir.is_dir():
        return verdicts
    for path in gate_dir.glob("*.json"):
        data = _load_json(path)
        if data and data.get("target"):
            verdicts[data["target"]] = data
    return verdicts


def _escape(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        str(text).replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _breakable(text: str) -> str:
    """Escape *text* and allow line breaks after _ / . so names never split mid-word."""
    out = _escape(text)
    for ch in ("_", "/", "."):
        out = out.replace(ch, ch + "<wbr>")
    return out


def _read_witness_source(witness_file: str, repo_root: Path | None) -> str:
    """Return the source text of the witness file, or empty string."""
    if not witness_file or repo_root is None:
        return ""
    try:
        p = repo_root / witness_file
        if p.exists():
            return p.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def _gate_rules_html(verdict: dict, body_start: int = 0, body_end: int = 0) -> str:
    """Return the six gate rules with their result for *verdict*."""
    reason = verdict.get("reason")
    failed_idx = next((i for i, (k, _) in enumerate(_GATE_RULES) if k == reason), None)
    if reason == "timeout":
        failed_idx = 0
    executed = verdict.get("body_lines_executed") or []
    items = []
    for idx, (rule_key, rule_desc) in enumerate(_GATE_RULES):
        if failed_idx is None or idx < failed_idx:
            cls, name = "ok", "check"
        elif idx == failed_idx:
            cls, name = "fail", "x"
        else:
            cls, name = "skip", "minus"
        note = ""
        if rule_key == "body_not_executed" and executed and body_start and body_end:
            note = (f"<small class=\"nums\">{len(executed)} of {body_end - body_start + 1} "
                    f"body lines ran (lines {body_start} to {body_end})</small>")
        items.append(f'<li class="{cls}">{icon(name)}<span>{_escape(rule_desc)}{note}</span></li>')
    return '<ul class="rules">' + "".join(items) + "</ul>"


def _count_class(n: int, level: str) -> str:
    return "n0" if n == 0 else f"n-{level}"


def _detail_html(i: int, rec: dict, verdict: dict, repo_root: Path | None, hidden: bool) -> str:
    qualname = rec.get("qualname", "")
    level = rec.get("level", "unwitnessed")
    label = _LEVEL_STYLE.get(level, ("unknown", "", True))[0]
    seen_by = rec.get("seen_by", [])
    if level == "agent_witnessed":
        seen_text = "an IBM Bob witness that passed the gate"
    elif seen_by:
        seen_text = ", ".join(_BASELINE_NAMES.get(s, f"baseline {s}") for s in seen_by)
    else:
        seen_text = "nothing: no baseline ran it"
    facts = [
        ("change", rec.get("change", "")),
        ("file", rec.get("file", "")),
        ("seen by", seen_text),
    ]
    witness_html = ""
    if level == "agent_witnessed" and verdict:
        facts.append(("witness file", verdict.get("witness", "")))
        facts.append(("gate verdict", "accepted" if verdict.get("accepted") else f"rejected: {verdict.get('reason')}"))
        src = _read_witness_source(verdict.get("witness", ""), repo_root)
        code = f'<pre class="code">{_escape(src)}</pre>' if src else ""
        witness_html = (
            '<div class="witness">'
            f"{code}"
            f'<div><span class="eyebrow rules-label">Gate rules</span>'
            f'{_gate_rules_html(verdict, rec.get("body_start", 0), rec.get("body_end", 0))}</div>'
            "</div>"
        )
    facts_html = "".join(f"<dt>{_escape(k)}</dt><dd>{_breakable(v)}</dd>" for k, v in facts)
    return (
        f'<div class="detail" id="detail-{i}" role="region" aria-label="Detail for {_escape(qualname)}"'
        f'{" hidden" if hidden else ""}>'
        f'<div class="detail__head"><span class="detail__name">{_breakable(qualname)}</span>'
        f'<span class="pill pill--{_escape(level)}">{_escape(label)}</span></div>'
        f'<dl class="facts">{facts_html}</dl>'
        f"{witness_html}</div>"
    )


def _bob_section(hunt: dict | None, gate_verdicts: dict[str, dict], remote_url: str) -> str:
    if not hunt:
        return ""
    subagents = hunt.get("subagent_bobcoins", [])
    accepted = sum(1 for v in gate_verdicts.values() if v.get("accepted"))
    # Bob's task cost already includes the subagents it started.
    total_cost = hunt.get("task_bobcoins", 0)
    per_witness = total_cost / accepted if accepted else 0
    shots = f"{remote_url}/tree/main/bob_sessions" if remote_url else "bob_sessions/"
    note_html = f"<span>{_escape(hunt['note'])}</span>" if hunt.get("note") else ""
    steps = [
        ("crosshair-simple", "Witness mode",
         "A custom Bob mode whose file edits are restricted to witnesses/*.py."),
        ("git-fork", f"{len(subagents)} subagents in parallel",
         "One per function nobody had seen running. Each follows the witness-hunt skill."),
        ("seal-check", f"{accepted} of {len(gate_verdicts)} accepted by the gate",
         "Each witness had to pass all six rules before the function was promoted."),
    ]
    steps_html = "".join(
        f'<div class="step"><div class="step__top">{icon(ic)}<span class="step__n">0{n}</span></div>'
        f'<p class="step__title">{_escape(t)}</p><p class="step__text">{_escape(d)}</p></div>'
        for n, (ic, t, d) in enumerate(steps, 1)
    )
    return (
        '<section class="section block" style="--i:5" aria-labelledby="bob-title">'
        '<div class="section__head"><h2 class="section__title" id="bob-title">How Bob closed the gap</h2></div>'
        f'<div class="steps">{steps_html}</div>'
        '<div class="cost">'
        f'<span class="cost__main nums">{icon("coins")}{total_cost:.3f} Bobcoins for the whole hunt, '
        f"{per_witness:.2f} per witness</span>"
        f"{note_html}"
        f'<a class="textlink" href="{_escape(shots)}">Bob session screenshots {icon("arrow-up-right")}</a>'
        "</div></section>"
    )


def _history_section(history: dict | None, remote_url: str) -> str:
    if not history or "commits_measured_with_changed_functions" not in history:
        return ""
    measured = history["commits_measured_with_changed_functions"]
    fired = history["commits_with_a_never_run_function"]
    upstream = history.get("upstream", "").rstrip("/")
    flagged = [r for r in history.get("records", []) if r.get("never")]
    links = ", ".join(
        f'<a class="textlink" href="{_escape(upstream)}/commit/{_escape(r["commit"])}">{_escape(r["commit"])}</a>'
        for r in flagged
    )
    bench = f"{remote_url}/blob/main/bench/history.py" if remote_url else "bench/history.py"
    return (
        '<section class="section block" style="--i:7" aria-labelledby="hist-title">'
        '<div class="section__head"><h2 class="section__title" id="hist-title">Across the project\'s history</h2>'
        f'<span class="eyebrow nums">{history.get("commits_in_range", 0)} commits replayed, '
        f'{history.get("commits_skipped", 0)} skipped</span></div>'
        '<div class="history">'
        f'<div><p class="history__count nums"><span class="{"is-alert" if fired else "is-zero"}">{fired}</span>'
        f'<span class="of"> of {measured}</span></p>'
        '<p class="history__sub">commits changed a function their own tests never ran</p></div>'
        '<div class="history__facts">'
        f'<p class="row nums">{icon("clock-counter-clockwise")}<span><b>{history.get("changed_functions_never_run", 0)} of '
        f'{history.get("changed_functions", 0)}</b> changed functions never ran under the suite of their own commit.</span></p>'
        f'<p class="row">{icon("arrow-up-right")}<span>Flagged: {links or "none"}. '
        "Every other commit raised nothing. This counts alarms; the history has no ground truth for gaps nobody noticed.</span></p>"
        f'<p class="row">{icon("check")}<span>Measured with Witnessed\'s own library by '
        f'<a class="textlink" href="{_escape(bench)}">bench/history.py</a>, written by Claude (Anthropic), not by Bob.</span></p>'
        "</div></div></section>"
    )


_MARK_SVG = (
    '<svg class="brand__mark" viewBox="0 0 28 28" fill="none" aria-hidden="true">'
    '<rect x="1.75" y="1.75" width="24.5" height="24.5" rx="3" stroke="var(--lamp)" stroke-width="1.5"/>'
    '<rect x="6.5" y="6.5" width="15" height="15" rx="1.5" stroke="var(--dim)" stroke-width="1.5" stroke-dasharray="2.5 2.5"/>'
    '<circle cx="14" cy="14" r="3" fill="var(--lamp)"/></svg>'
)


def build_report(
    scan_data: dict,
    gate_verdicts: dict[str, dict],
    commit_message: str,
    *,
    repo_root: Path | None = None,
    remote_url: str = "",
    hunt: dict | None = None,
    history: dict | None = None,
) -> str:
    """Return the full HTML string for the report."""
    counts_after: dict[str, int] = {lv: scan_data.get("counts", {}).get(lv, 0) for lv in _LEVEL_ORDER}
    changed: list[dict] = sorted(
        scan_data.get("changed", []),
        key=lambda r: _CELL_ORDER.get(r.get("level", "unwitnessed"), 9),
    )
    total = len(changed)
    head_sha: str = scan_data.get("head", "")

    counts_before = dict(counts_after)
    counts_before["unwitnessed"] = counts_after["unwitnessed"] + counts_after["agent_witnessed"]
    counts_before["agent_witnessed"] = 0
    before_n = counts_before["unwitnessed"]
    after_n = counts_after["unwitnessed"]
    witnessed_n = counts_after["agent_witnessed"]

    trailers = _parse_git_trailers(commit_message)
    upstream_repo = trailers.get("Upstream-Repo", "")
    upstream_commit = trailers.get("Upstream-Commit", "")
    if upstream_repo and upstream_commit:
        repo_name = upstream_repo.rstrip("/").split("/")[-1]
        meta_html = (
            f'<a class="meta-link" href="{_escape(upstream_repo.rstrip("/"))}/commit/{_escape(upstream_commit)}">'
            f"{_escape(repo_name)}, upstream {_escape(upstream_commit[:7])} {icon('arrow-up-right')}</a>"
        )
    else:
        meta_html = f'<span class="meta-link">{_escape(head_sha[:7])}</span>' if head_sha else ""

    default_idx = next(
        (i for i, r in enumerate(changed) if r.get("level") in ("agent_witnessed", "unwitnessed")), 0
    )
    cells_html = ""
    details_html = ""
    for i, rec in enumerate(changed):
        qualname = rec.get("qualname", "")
        level = rec.get("level", "unwitnessed")
        label = _LEVEL_STYLE.get(level, ("unknown", "", True))[0]
        pressed = "true" if i == default_idx else "false"
        cells_html += (
            f'<button type="button" class="cell cell--{_escape(level)}" aria-pressed="{pressed}" '
            f'aria-controls="detail-{i}" data-i="{i}" style="--stagger:{min(i, 7)}">'
            f'<span class="cell__name">{_breakable(qualname.split(".")[-1])}</span>'
            f'<span class="cell__level">{_escape(label)}</span></button>'
        )
        details_html += _detail_html(i, rec, gate_verdicts.get(qualname, {}), repo_root, i != default_idx)

    legend_html = "".join(
        f'<span class="legend__item nums{" is-empty" if counts_after[lv] == 0 else ""}">'
        f'<span class="swatch swatch--{lv}"></span>{_escape(_LEVEL_STYLE[lv][0])} <b>{counts_after[lv]}</b></span>'
        for lv in _LEVEL_ORDER
    )
    rows_html = "".join(
        f'<tr><td><span class="row-label"><span class="swatch swatch--{lv}"></span>{_escape(_LEVEL_STYLE[lv][0])}</span></td>'
        f'<td class="{_count_class(counts_before[lv], lv)}">{counts_before[lv]}</td>'
        f'<td class="{_count_class(counts_after[lv], lv)}">{counts_after[lv]}</td></tr>'
        for lv in _LEVEL_ORDER
    )
    commit_lines = _strip_trailers(commit_message, trailers).splitlines()
    commit_html = f'<pre class="commit">{_escape(chr(10).join(commit_lines[:_COMMIT_PREVIEW_LINES])) or "(no commit message)"}</pre>'
    if len(commit_lines) > _COMMIT_PREVIEW_LINES:
        rest = commit_lines[_COMMIT_PREVIEW_LINES:]
        commit_html += (
            f'<details class="more"><summary class="nums">Show the rest of the message, {len(rest)} more lines</summary>'
            f'<pre class="commit">{_escape(chr(10).join(rest))}</pre></details>'
        )

    bob_line = ""
    if witnessed_n:
        bob_line = f'<p class="hero__bob nums">{icon("seal-check")}{witnessed_n} witnessed by Bob, gate accepted</p>'
    footer_link = (
        f'<a class="textlink" href="{_escape(remote_url)}">{_escape(remote_url.replace("https://", ""))}</a>'
        if remote_url else "<span></span>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Witnessed report</title>
<meta name="description" content="Which functions a change touched that nobody has ever seen running, and the witnesses IBM Bob wrote for them.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 28 28'%3E%3Crect width='28' height='28' rx='4' fill='%230F1215'/%3E%3Crect x='3' y='3' width='22' height='22' rx='3' fill='none' stroke='%23F2B544' stroke-width='2'/%3E%3Ccircle cx='14' cy='14' r='4' fill='%23F2B544'/%3E%3C/svg%3E">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>{REPORT_CSS}</style>
</head>
<body>
<main class="wrap">

  <header class="header block" style="--i:0">
    <div class="brand">{_MARK_SVG}<span class="brand__name">witnessed</span></div>
    {meta_html}
  </header>
  <p class="tagline block" style="--i:1">Witnessed finds the functions a change touched that <strong>nobody has ever seen running</strong>, and sends IBM Bob to write a witness for each one: a small script that calls the real function and must pass a six-rule gate.</p>

  <section class="hero block" style="--i:2" aria-label="Before and after Bob">
    <div>
      <p class="eyebrow">Before Bob</p>
      <p class="hero__count nums"><span class="{"is-alert" if before_n else "is-zero"}">{before_n}</span><span class="of"> of {total}</span></p>
      <p class="hero__sub">changed functions never seen running</p>
    </div>
    <div>
      <p class="eyebrow">After Bob</p>
      <p class="hero__count nums"><span class="{"is-alert" if after_n else "is-zero"}">{after_n}</span><span class="of"> of {total}</span></p>
      <p class="hero__sub">changed functions never seen running</p>
      {bob_line}
    </div>
    <span hidden>{before_n} of {total} changed functions were never seen running</span>
    <span hidden>after gate: {after_n} of {total} still unwitnessed</span>
  </section>

  <section class="section block" style="--i:3" aria-labelledby="fn-title">
    <div class="section__head">
      <h2 class="section__title nums" id="fn-title">The {total} functions this change touched</h2>
      <div class="legend">{legend_html}</div>
    </div>
    <div class="grid" role="group" aria-label="Changed functions, select one to see its evidence">{cells_html}</div>
    {details_html}
  </section>

  {_bob_section(hunt, gate_verdicts, remote_url)}

  <section class="section block" style="--i:6" aria-label="The change and what ran">
    <div class="context">
      <div class="card"><span class="eyebrow">What the change said</span>{commit_html}</div>
      <div class="card"><span class="eyebrow">What actually ran</span>
        <table class="counts nums">
          <tr><th scope="col">level</th><th scope="col">before Bob</th><th scope="col">after Bob</th></tr>
          {rows_html}
          <tr class="total"><td>total changed</td><td>{total}</td><td>{total}</td></tr>
        </table>
      </div>
    </div>
  </section>

  {_history_section(history, remote_url)}

  <footer class="footer">{footer_link}<span>Made with IBM Bob</span></footer>
</main>
<script>
(function () {{
  var cells = document.querySelectorAll('.cell');
  cells.forEach(function (btn) {{
    btn.addEventListener('click', function () {{
      cells.forEach(function (c) {{
        var on = c === btn;
        c.setAttribute('aria-pressed', on ? 'true' : 'false');
        document.getElementById('detail-' + c.dataset.i).hidden = !on;
      }});
    }});
  }});
}})();
</script>
</body>
</html>"""


def generate_report(repo_root: Path) -> Path:
    """Read inputs, build the HTML, write docs/report.html and docs/index.html, and return the report path."""
    witnessed_dir = repo_root / ".witnessed"
    scan_data = json.loads((witnessed_dir / "scan.json").read_text(encoding="utf-8"))
    gate_verdicts = _load_gate_verdicts(witnessed_dir / "gate")

    head_sha = scan_data.get("head", "HEAD")
    html = build_report(
        scan_data,
        gate_verdicts,
        _head_commit_message(head_sha, repo_root),
        repo_root=repo_root,
        remote_url=_remote_url(repo_root),
        hunt=_load_json(repo_root / "bob_sessions" / "witness_hunt.json"),
        history=_load_json(repo_root / "bench" / "history.json"),
    )

    out_dir = repo_root / "docs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "report.html"
    out_path.write_text(html, encoding="utf-8")
    (out_dir / "index.html").write_text(html, encoding="utf-8")
    return out_path
