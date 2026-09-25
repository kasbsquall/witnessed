"""Generate docs/report.html from .witnessed/scan.json and gate verdicts."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


# Level display config: (label, fill_color, outline_only)
_LEVEL_STYLE: dict[str, tuple[str, str, bool]] = {
    "used":            ("used in real runs",          "#F2B544", False),
    "tested":          ("only by tests",              "#8A7A55", False),
    "agent_witnessed": ("witnessed by an agent",      "#F2B544", True),
    "unwitnessed":     ("never seen running",         "#333333", True),
}


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


def _load_gate_verdicts(gate_dir: Path) -> dict[str, dict]:
    """Return a mapping qualname -> verdict dict for every .json in gate_dir."""
    verdicts: dict[str, dict] = {}
    if not gate_dir.is_dir():
        return verdicts
    for path in gate_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            target = data.get("target", "")
            if target:
                verdicts[target] = data
        except Exception:
            pass
    return verdicts


def _escape(text: str) -> str:
    """Minimal HTML escaping."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def build_report(
    scan_data: dict,
    gate_verdicts: dict[str, dict],
    commit_message: str,
) -> str:
    """Return the full HTML string for the report."""
    counts_after: dict[str, int] = scan_data.get("counts", {})
    changed: list[dict] = scan_data.get("changed", [])
    total = len(changed)
    head_sha: str = scan_data.get("head", "")
    sample_name: str = scan_data.get("sample", "")

    # "Before" counts: agent_witnessed units were unwitnessed before the gate.
    before_unwitnessed = counts_after.get("unwitnessed", 0) + counts_after.get("agent_witnessed", 0)
    after_unwitnessed = counts_after.get("unwitnessed", 0)

    short_sha = head_sha[:7] if head_sha else ""

    counts_used = counts_after.get("used", 0)
    counts_tested = counts_after.get("tested", 0)
    counts_agent = counts_after.get("agent_witnessed", 0)
    counts_unwit = counts_after.get("unwitnessed", 0)

    # ------------------------------------------------------------------
    # Build cell HTML for each changed function.
    # ------------------------------------------------------------------
    cells_html = ""
    first_unwitnessed_idx = -1
    for i, rec in enumerate(changed):
        level = rec.get("level", "unwitnessed")
        if level in ("unwitnessed", "agent_witnessed") and first_unwitnessed_idx == -1:
            first_unwitnessed_idx = i

    for i, rec in enumerate(changed):
        qualname = rec.get("qualname", "")
        level = rec.get("level", "unwitnessed")
        change = rec.get("change", "")
        seen_by = rec.get("seen_by", [])
        label, _color, _outline = _LEVEL_STYLE.get(level, ("unknown", "#999", True))

        verdict = gate_verdicts.get(qualname, {})
        witness_file = verdict.get("witness", "") if verdict else ""
        gate_accepted = verdict.get("accepted", False) if verdict else False
        gate_reason = verdict.get("reason") if verdict else None

        short_name = qualname.split(".")[-1] if "." in qualname else qualname
        seen_text = ", ".join(seen_by) if seen_by else "none"

        gate_html = ""
        if level == "agent_witnessed":
            gate_status = "accepted" if gate_accepted else f"rejected: {gate_reason}"
            gate_html = f"""
              <dt>witness file</dt><dd>{_escape(witness_file)}</dd>
              <dt>gate verdict</dt><dd>{_escape(gate_status)}</dd>"""

        stagger_idx = min(i, 7)
        is_default = "true" if i == first_unwitnessed_idx else "false"

        cells_html += f"""
      <button class="cell cell--{_escape(level)}" id="btn-{i}"
              aria-pressed="{is_default}"
              data-qualname="{_escape(qualname)}"
              data-change="{_escape(change)}"
              data-level="{_escape(label)}"
              data-seen="{_escape(seen_text)}"
              data-witness="{_escape(witness_file)}"
              data-gate="{_escape(('accepted' if gate_accepted else ('rejected: ' + str(gate_reason))) if level == 'agent_witnessed' else '')}"
              style="--stagger:{stagger_idx}">
        <span class="cell__name">{_escape(short_name)}</span>
        <span class="cell__level">{_escape(label)}</span>
      </button>"""

    # ------------------------------------------------------------------
    # Commit message
    # ------------------------------------------------------------------
    commit_msg_html = _escape(commit_message) if commit_message else "(no commit message)"

    # ------------------------------------------------------------------
    # Header meta line
    # ------------------------------------------------------------------
    meta_parts = []
    if short_sha:
        meta_parts.append(_escape(short_sha))
    if sample_name:
        meta_parts.append(_escape(sample_name))
    meta_line = "  /  ".join(meta_parts) if meta_parts else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Witnessed Report</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,600;12..96,700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {{
  --ink: #0F1215;
  --cell: #1D2228;
  --line: rgba(233,229,220,0.08);
  --text: #E9E5DC;
  --muted: #8B9097;
  --dim: #3A4149;
  --lamp: #F2B544;
  --tested: #8A7A55;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ background: var(--ink); color: var(--text); }}
body {{
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 14px;
  line-height: 1.6;
  background: var(--ink);
  color: var(--text);
  padding: 32px 16px 64px;
  min-height: 100vh;
}}
.wrap {{ max-width: 960px; margin: 0 auto; }}

/* --- numbers --- */
.nums {{ font-variant-numeric: tabular-nums lining-nums slashed-zero; }}

/* ================================================================
   HEADER
   ================================================================ */
.header {{
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 56px;
}}
.header__brand {{
  display: flex;
  align-items: center;
  gap: 12px;
}}
.header__mark {{ display: block; width: 36px; height: 36px; flex-shrink: 0; }}
.header__title {{
  font-family: "Bricolage Grotesque", Georgia, serif;
  font-weight: 600;
  font-size: 26px;
  letter-spacing: -0.02em;
  color: var(--text);
  line-height: 1;
}}
.header__meta {{
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--muted);
}}

/* ================================================================
   HERO
   ================================================================ */
.hero {{ margin-bottom: 64px; }}
.hero__label {{
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--muted);
  margin-bottom: 4px;
}}
.hero__count {{
  font-family: "Bricolage Grotesque", Georgia, serif;
  font-weight: 700;
  font-size: 88px;
  line-height: 0.9;
  letter-spacing: -0.035em;
  font-variant-numeric: tabular-nums lining-nums slashed-zero;
  margin-bottom: 8px;
}}
.hero__count .n-lamp {{ color: var(--lamp); }}
.hero__count .n-text {{ color: var(--text); }}
.hero__after {{
  font-size: 14px;
  color: var(--muted);
  font-variant-numeric: tabular-nums lining-nums slashed-zero;
}}

/* ================================================================
   LEGEND
   ================================================================ */
.legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px 24px;
  margin-bottom: 32px;
}}
.legend__item {{
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
}}
.legend__swatch {{
  width: 14px;
  height: 14px;
  border-radius: 3px;
  flex-shrink: 0;
}}
.legend__swatch--used    {{ background: var(--lamp); border: 1.5px solid var(--lamp); }}
.legend__swatch--tested  {{ background: var(--tested); border: 1.5px solid var(--tested); }}
.legend__swatch--agent   {{ background: var(--cell); border: 1.5px solid var(--lamp); }}
.legend__swatch--unwit   {{ background: var(--cell); border: 1.5px dashed var(--muted); }}

/* ================================================================
   CELLS GRID
   ================================================================ */
.grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 8px;
  margin-bottom: 24px;
}}
.cell {{
  height: 64px;
  padding: 12px;
  border-radius: 3px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 3px;
  text-align: left;
  background: none;
  transition: border-color 120ms ease, transform 80ms ease;
}}
.cell__name {{
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}}
.cell__level {{
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 11px;
  display: block;
}}
/* filled cells */
.cell--used, .cell--tested {{
  color: var(--ink);
}}
.cell--used   {{ background: var(--lamp);   border: 1.5px solid var(--lamp); }}
.cell--tested {{ background: var(--tested); border: 1.5px solid var(--tested); }}
/* outlined cells */
.cell--agent_witnessed, .cell--unwitnessed {{
  color: var(--text);
}}
.cell--agent_witnessed {{ background: var(--cell); border: 1.5px solid var(--lamp); }}
.cell--unwitnessed     {{ background: var(--cell); border: 1.5px dashed var(--muted); }}

/* hover */
.cell--used:hover            {{ border-color: #f5c76a; }}
.cell--tested:hover          {{ border-color: #a08e6e; }}
.cell--agent_witnessed:hover {{ border-color: #f5c76a; }}
.cell--unwitnessed:hover     {{ border-color: #a8b0b8; }}

/* active */
.cell:active {{ transform: scale(0.98); }}

/* focus */
.cell:focus-visible {{
  outline: 2px solid var(--lamp);
  outline-offset: 2px;
}}

/* selected */
.cell[aria-pressed="true"].cell--used            {{ background: #f5c76a; border-color: #f5c76a; }}
.cell[aria-pressed="true"].cell--tested          {{ background: #a08e6e; border-color: #a08e6e; }}
.cell[aria-pressed="true"].cell--agent_witnessed {{ border-color: #f5c76a; border-width: 2px; }}
.cell[aria-pressed="true"].cell--unwitnessed     {{ border-color: #a8b0b8; border-width: 2px; }}

/* ================================================================
   DETAIL PANEL
   ================================================================ */
.detail {{
  background: var(--cell);
  border-radius: 3px;
  border: 1px solid var(--line);
  padding: 20px;
  margin-bottom: 64px;
}}
.detail dl {{
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 6px 24px;
}}
.detail dt {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--muted);
  padding-top: 1px;
}}
.detail dd {{
  font-size: 13px;
  color: var(--text);
  overflow-wrap: anywhere;
}}

/* ================================================================
   CONTEXT
   ================================================================ */
.context {{
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 16px;
  margin-bottom: 48px;
}}
@media (max-width: 719px) {{
  .context {{ grid-template-columns: minmax(0, 1fr); }}
}}
.context__card {{
  background: var(--cell);
  border-radius: 3px;
  border: 1px solid var(--line);
  padding: 20px;
  min-width: 0;
}}
.context__label {{
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--muted);
  margin-bottom: 12px;
  display: block;
}}
.commit-msg {{
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 12.5px;
  color: var(--text);
  white-space: pre;
  max-height: 360px;
  overflow: auto;
  margin: 0;
}}
.counts-table {{
  width: 100%;
  border-collapse: collapse;
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 13px;
  font-variant-numeric: tabular-nums lining-nums slashed-zero;
}}
.counts-table td {{ padding: 3px 0; }}
.counts-table td:first-child {{ color: var(--muted); padding-right: 24px; }}
.counts-table td:last-child {{ text-align: right; color: var(--text); }}
.counts-table tr.total td {{ border-top: 1px solid var(--line); padding-top: 8px; }}

/* ================================================================
   FOOTER
   ================================================================ */
.footer {{
  text-align: center;
  font-size: 12px;
  color: var(--muted);
  border-top: 1px solid var(--line);
  padding-top: 12px;
}}

/* ================================================================
   MOTION
   ================================================================ */
@media (prefers-reduced-motion: no-preference) {{
  @keyframes rise {{
    from {{ opacity: 0; transform: translateY(6px); }}
    to   {{ opacity: 1; transform: none; }}
  }}
  .block {{
    animation: rise 220ms ease both;
    animation-delay: calc(var(--delay, 0) * 1ms);
  }}
  .cell {{
    animation: rise 200ms ease both;
    animation-delay: calc(var(--stagger, 0) * 30ms + 120ms);
  }}
}}

@media (max-width: 375px) {{
  body {{ padding-left: 16px; padding-right: 16px; overflow-x: hidden; }}
}}
</style>
</head>
<body>
<div class="wrap">

  <!-- HEADER -->
  <header class="header block" style="--delay:0">
    <div class="header__brand">
      <svg class="header__mark" viewBox="0 0 84 84" fill="none" aria-hidden="true">
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(0   42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(60  42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(90  42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(120 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(150 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(180 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(210 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(240 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(270 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(300 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--dim)"   stroke-width="5.5" stroke-linecap="round" transform="rotate(330 42 42)"/>
        <line x1="42" y1="4" x2="42" y2="15" stroke="var(--lamp)"  stroke-width="7"   stroke-linecap="round" transform="rotate(30  42 42)"/>
      </svg>
      <span class="header__title">witnessed</span>
    </div>
    {f'<span class="header__meta">{meta_line}</span>' if meta_line else ""}
  </header>

  <!-- HERO -->
  <section class="hero block" style="--delay:60" aria-label="Coverage summary">
    <p class="hero__label">changed functions never seen running</p>
    <p class="hero__count nums" aria-label="{before_unwitnessed} of {total} changed functions were never seen running">
      <span class="n-lamp">{before_unwitnessed}</span><span class="n-text"> of {total}</span>
    </p>
    <p class="hero__after nums">after Bob's witnesses: {after_unwitnessed} of {total}</p>
    <!-- search text for tests -->
    <span hidden>{before_unwitnessed} of {total} changed functions were never seen running</span>
    <span hidden>after gate: {after_unwitnessed} of {total} still unwitnessed</span>
  </section>

  <!-- LEGEND -->
  <div class="legend block" style="--delay:120">
    <div class="legend__item">
      <span class="legend__swatch legend__swatch--used" aria-hidden="true"></span>
      <span>used in real runs</span>
    </div>
    <div class="legend__item">
      <span class="legend__swatch legend__swatch--tested" aria-hidden="true"></span>
      <span>only by tests</span>
    </div>
    <div class="legend__item">
      <span class="legend__swatch legend__swatch--agent" aria-hidden="true"></span>
      <span>witnessed by an agent</span>
    </div>
    <div class="legend__item">
      <span class="legend__swatch legend__swatch--unwit" aria-hidden="true"></span>
      <span>never seen running</span>
    </div>
  </div>

  <!-- CELLS GRID -->
  <div class="grid block" style="--delay:180" id="fn-grid" role="group" aria-label="Changed functions">
{cells_html}
  </div>

  <!-- DETAIL PANEL -->
  <div class="detail block" style="--delay:240" id="fn-detail" aria-live="polite" role="region" aria-label="Function detail">
    <dl>
      <dt>qualname</dt><dd id="d-qualname" class="nums">--</dd>
      <dt>change type</dt><dd id="d-change">--</dd>
      <dt>level</dt><dd id="d-level">--</dd>
      <dt>seen by</dt><dd id="d-seen">--</dd>
      <dt id="d-witness-label" hidden>witness file</dt><dd id="d-witness" hidden></dd>
      <dt id="d-gate-label" hidden>gate verdict</dt><dd id="d-gate" hidden></dd>
    </dl>
  </div>

  <!-- CONTEXT -->
  <div class="context block" style="--delay:300">
    <div class="context__card">
      <span class="context__label">What the change said</span>
      <pre class="commit-msg">{commit_msg_html}</pre>
    </div>
    <div class="context__card">
      <span class="context__label">What actually ran</span>
      <table class="counts-table nums">
        <tr><td>used in real runs</td><td>{counts_used}</td></tr>
        <tr><td>only by tests</td><td>{counts_tested}</td></tr>
        <tr><td>witnessed by an agent</td><td>{counts_agent}</td></tr>
        <tr><td>never seen running</td><td>{counts_unwit}</td></tr>
        <tr class="total"><td>total changed</td><td>{total}</td></tr>
      </table>
    </div>
  </div>

  <!-- FOOTER -->
  <footer class="footer block" style="--delay:360">Made with IBM Bob</footer>

</div>

<script>
(function () {{
  var cells = document.querySelectorAll('.cell');
  var detail = document.getElementById('fn-detail');
  var dQname   = document.getElementById('d-qualname');
  var dChange  = document.getElementById('d-change');
  var dLevel   = document.getElementById('d-level');
  var dSeen    = document.getElementById('d-seen');
  var dWLabel  = document.getElementById('d-witness-label');
  var dWit     = document.getElementById('d-witness');
  var dGLabel  = document.getElementById('d-gate-label');
  var dGate    = document.getElementById('d-gate');

  function selectCell(btn) {{
    cells.forEach(function (c) {{ c.setAttribute('aria-pressed', 'false'); }});
    btn.setAttribute('aria-pressed', 'true');
    dQname.textContent  = btn.dataset.qualname || '--';
    dChange.textContent = btn.dataset.change   || '--';
    dLevel.textContent  = btn.dataset.level    || '--';
    dSeen.textContent   = btn.dataset.seen     || '--';
    var wit  = btn.dataset.witness || '';
    var gate = btn.dataset.gate    || '';
    if (wit) {{
      dWLabel.hidden = false; dWit.hidden = false; dWit.textContent = wit;
    }} else {{
      dWLabel.hidden = true;  dWit.hidden = true;  dWit.textContent = '';
    }}
    if (gate) {{
      dGLabel.hidden = false; dGate.hidden = false; dGate.textContent = gate;
    }} else {{
      dGLabel.hidden = true;  dGate.hidden = true;  dGate.textContent = '';
    }}
  }}

  cells.forEach(function (btn) {{
    btn.addEventListener('click', function () {{ selectCell(btn); }});
  }});

  // Select the first cell that is aria-pressed="true" on load.
  var def = document.querySelector('.cell[aria-pressed="true"]');
  if (!def && cells.length) {{ def = cells[0]; }}
  if (def) {{ selectCell(def); }}
}})();
</script>
</body>
</html>"""
    return html


def generate_report(repo_root: Path) -> Path:
    """Read inputs, build the HTML, write docs/report.html, and return the path."""
    witnessed_dir = repo_root / ".witnessed"
    scan_path = witnessed_dir / "scan.json"
    gate_dir = witnessed_dir / "gate"

    scan_data = json.loads(scan_path.read_text(encoding="utf-8"))
    gate_verdicts = _load_gate_verdicts(gate_dir)

    head_sha = scan_data.get("head", "HEAD")
    commit_message = _head_commit_message(head_sha, repo_root)

    html = build_report(scan_data, gate_verdicts, commit_message)

    out_dir = repo_root / "docs"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "report.html"
    out_path.write_text(html, encoding="utf-8")
    return out_path
