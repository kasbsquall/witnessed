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


def _cell_style(level: str) -> str:
    """Return inline CSS for the cell button."""
    _label, color, outline_only = _LEVEL_STYLE.get(
        level, ("unknown", "#999999", True)
    )
    if outline_only:
        return (
            f"background:#fff;border:2px solid {color};color:#1f2328;"
            "border-radius:4px;padding:6px 10px;cursor:pointer;"
            "font-size:12px;font-family:inherit;text-align:left;width:100%;"
        )
    else:
        return (
            f"background:{color};border:2px solid {color};color:#fff;"
            "border-radius:4px;padding:6px 10px;cursor:pointer;"
            "font-size:12px;font-family:inherit;text-align:left;width:100%;"
        )


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

    # "Before" counts: agent_witnessed units were unwitnessed before the gate.
    before_unwitnessed = counts_after.get("unwitnessed", 0) + counts_after.get("agent_witnessed", 0)

    after_unwitnessed = counts_after.get("unwitnessed", 0)

    # Build cell HTML for each changed function.
    cells_html = ""
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

        detail_id = f"detail-{i}"
        btn_id = f"btn-{i}"
        style = _cell_style(level)

        seen_text = ", ".join(seen_by) if seen_by else "none"

        gate_html = ""
        if level == "agent_witnessed":
            gate_status = "accepted" if gate_accepted else f"rejected: {gate_reason}"
            gate_html = f"""
              <tr><td>witness file</td><td>{_escape(witness_file)}</td></tr>
              <tr><td>gate verdict</td><td>{_escape(gate_status)}</td></tr>"""

        detail_html = f"""
        <div id="{detail_id}" role="region" aria-labelledby="{btn_id}"
             style="display:none;margin-top:6px;padding:10px;background:#f7f8fa;
                    border:1px solid #e5e7eb;border-radius:4px;font-size:13px;">
          <table style="border-collapse:collapse;width:100%;">
            <tr><td style="padding:2px 8px 2px 0;color:#57606a;width:140px;">qualname</td>
                <td style="padding:2px 0;font-family:monospace;">{_escape(qualname)}</td></tr>
            <tr><td style="padding:2px 8px 2px 0;color:#57606a;">change type</td>
                <td style="padding:2px 0;">{_escape(change)}</td></tr>
            <tr><td style="padding:2px 8px 2px 0;color:#57606a;">level</td>
                <td style="padding:2px 0;">{_escape(label)}</td></tr>
            <tr><td style="padding:2px 8px 2px 0;color:#57606a;">seen by</td>
                <td style="padding:2px 0;">{_escape(seen_text)}</td></tr>{gate_html}
          </table>
        </div>"""

        short_name = qualname.split(".")[-1] if "." in qualname else qualname

        cells_html += f"""
      <div style="margin-bottom:8px;">
        <button id="{btn_id}" style="{style}"
                aria-expanded="false" aria-controls="{detail_id}"
                onclick="toggleDetail('{detail_id}','{btn_id}')">{_escape(short_name)}</button>{detail_html}
      </div>"""

    # Legend
    legend_html = ""
    for lv, (label, color, outline) in _LEVEL_STYLE.items():
        if outline:
            swatch = (
                f"display:inline-block;width:14px;height:14px;border-radius:3px;"
                f"border:2px solid {color};background:#fff;vertical-align:middle;margin-right:6px;"
            )
        else:
            swatch = (
                f"display:inline-block;width:14px;height:14px;border-radius:3px;"
                f"border:2px solid {color};background:{color};vertical-align:middle;margin-right:6px;"
            )
        legend_html += (
            f'<div style="display:flex;align-items:center;margin-bottom:4px;">'
            f'<span style="{swatch}"></span>'
            f'<span style="font-size:13px;">{_escape(label)}</span>'
            f"</div>\n"
        )

    commit_msg_html = _escape(commit_message) if commit_message else "<em>(no commit message)</em>"
    # Preserve newlines in commit message.
    commit_msg_html = commit_msg_html.replace("\n", "<br>")

    counts_used = counts_after.get("used", 0)
    counts_tested = counts_after.get("tested", 0)
    counts_agent = counts_after.get("agent_witnessed", 0)
    counts_unwit = counts_after.get("unwitnessed", 0)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Witnessed Report</title>
<style>
* {{ box-sizing: border-box; }}
body {{
  font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.6;
  color: #1f2328;
  background: #ffffff;
  margin: 0;
  padding: 24px 16px 48px;
}}
.container {{ max-width: 760px; margin: 0 auto; }}
h1 {{ font-size: 20px; margin: 0 0 4px; }}
.subtitle {{ color: #57606a; margin: 0 0 24px; font-size: 14px; }}
.after-line {{ font-size: 13px; color: #57606a; margin: 4px 0 0; font-variant-numeric: tabular-nums; }}
h2 {{ font-size: 15px; margin: 24px 0 10px; border-bottom: 1px solid #e5e7eb; padding-bottom: 6px; }}
.two-col {{ display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 24px; }}
.two-col > div {{ flex: 1; min-width: 260px; background: #f7f8fa; border: 1px solid #e5e7eb;
                  border-radius: 6px; padding: 14px 16px; }}
.two-col h3 {{ font-size: 13px; margin: 0 0 8px; color: #57606a; text-transform: uppercase;
               letter-spacing: .04em; }}
.commit-msg {{ font-size: 13px; white-space: pre-wrap; word-break: break-word; }}
.counts-table {{ font-variant-numeric: tabular-nums; font-size: 14px; }}
.counts-table td {{ padding: 2px 0; }}
.counts-table td:first-child {{ color: #57606a; width: 160px; }}
.grid {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; }}
.grid > div {{ flex: 0 0 auto; width: calc(50% - 4px); }}
@media (min-width: 600px) {{ .grid > div {{ width: calc(33% - 6px); }} }}
.header-line {{ font-variant-numeric: tabular-nums; font-size: 18px; font-weight: 600; margin: 0 0 2px; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 12px 24px; margin-bottom: 24px; }}
hr {{ border: none; border-top: 1px solid #e5e7eb; margin: 24px 0; }}
.footer {{ text-align: center; font-size: 12px; color: #57606a;
           border-top: 1px solid #e5e7eb; padding-top: 12px; margin-top: 32px; }}
</style>
<script>
function toggleDetail(detailId, btnId) {{
  var d = document.getElementById(detailId);
  var b = document.getElementById(btnId);
  var open = d.style.display === 'block';
  d.style.display = open ? 'none' : 'block';
  b.setAttribute('aria-expanded', open ? 'false' : 'true');
}}
</script>
</head>
<body>
<div class="container">
  <p class="header-line">{before_unwitnessed} of {total} changed functions were never seen running</p>
  <p class="after-line">after gate: {after_unwitnessed} of {total} still unwitnessed</p>

  <h2>Legend</h2>
  <div class="legend">
{legend_html}  </div>

  <h2>Changed functions</h2>
  <div class="grid">{cells_html}
  </div>

  <h2>Context</h2>
  <div class="two-col">
    <div>
      <h3>What the change said</h3>
      <div class="commit-msg">{commit_msg_html}</div>
    </div>
    <div>
      <h3>What actually ran</h3>
      <table class="counts-table">
        <tr><td>used in real runs</td><td>{counts_used}</td></tr>
        <tr><td>only by tests</td><td>{counts_tested}</td></tr>
        <tr><td>witnessed by an agent</td><td>{counts_agent}</td></tr>
        <tr><td>never seen running</td><td>{counts_unwit}</td></tr>
        <tr><td style="padding-top:6px;font-weight:600;">total changed</td>
            <td style="padding-top:6px;font-weight:600;">{total}</td></tr>
      </table>
    </div>
  </div>

  <div class="footer">Made with IBM Bob</div>
</div>
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
