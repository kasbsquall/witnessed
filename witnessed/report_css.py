"""Stylesheet for docs/report.html. One meaning per color:
coral = never seen running, amber = witnessed by Bob, sand = only by tests,
bone = used in real runs, neutral text = zero or structure."""

REPORT_CSS = """
:root {
  --ink: #0F1215;
  --surface: #171B20;
  --raise: #1D2228;
  --line: rgba(233,229,220,0.08);
  --line-strong: rgba(233,229,220,0.16);
  --text: #E9E5DC;
  --muted: #8B9097;
  --dim: #4A525B;
  --lamp: #F2B544;
  --alert: #E0765A;
  --tested: #8A7A55;
  --used: #CFC9BC;
  --s1: 4px; --s2: 8px; --s3: 12px; --s4: 16px; --s5: 24px;
  --s6: 40px; --s7: 64px; --s8: 96px;
  --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { background: var(--ink); color: var(--text); }
body {
  font-family: "IBM Plex Mono", Consolas, monospace;
  font-size: 14px;
  line-height: 1.6;
  background: var(--ink);
  color: var(--text);
  padding: var(--s6) var(--s4) var(--s7);
  min-height: 100vh;
  overflow-x: hidden;
}
@media (min-width: 720px) {
  body { padding: var(--s7) var(--s6) var(--s8); }
}
.wrap { max-width: 1000px; margin: 0 auto; }
.nums { font-variant-numeric: tabular-nums lining-nums slashed-zero; }
a { color: inherit; }
a:focus-visible, button:focus-visible { outline: 2px solid var(--lamp); outline-offset: 3px; border-radius: 2px; }
.icon { width: 1em; height: 1em; flex-shrink: 0; display: inline-block; vertical-align: -0.125em; }
.eyebrow {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.16em;
  color: var(--muted);
}
.section { margin-top: var(--s8); }
.section__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--s2) var(--s5);
  margin-bottom: var(--s5);
}
.section__title {
  font-family: "Bricolage Grotesque", Georgia, serif;
  font-weight: 600;
  font-size: 22px;
  letter-spacing: -0.015em;
  line-height: 1.2;
  text-wrap: balance;
}

/* HEADER */
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--s3) var(--s5);
}
.brand { display: flex; align-items: center; gap: var(--s3); }
.brand__mark { width: 28px; height: 28px; display: block; }
.brand__name {
  font-family: "Bricolage Grotesque", Georgia, serif;
  font-weight: 700;
  font-size: 24px;
  letter-spacing: -0.02em;
  line-height: 1;
}
.meta-link {
  display: inline-flex;
  align-items: center;
  gap: var(--s1);
  text-decoration: none;
  color: var(--muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  transition: color 150ms var(--ease-out);
}
.meta-link:hover { color: var(--text); }
.tagline {
  margin-top: var(--s4);
  max-width: 64ch;
  font-size: 14px;
  color: var(--muted);
  text-wrap: pretty;
}
.tagline strong { color: var(--text); font-weight: 500; }

/* HERO */
.hero {
  margin-top: var(--s7);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--s6);
}
@media (min-width: 720px) {
  .hero { grid-template-columns: repeat(2, max-content); gap: var(--s8); }
}
.hero__count {
  margin-top: var(--s2);
  font-family: "Bricolage Grotesque", Georgia, serif;
  font-weight: 700;
  font-size: clamp(64px, 11vw, 96px);
  line-height: 0.86;
  letter-spacing: -0.035em;
  font-variant-numeric: tabular-nums lining-nums;
  white-space: nowrap;
}
.hero__count .of { color: var(--dim); }
.is-alert { color: var(--alert); }
.is-zero { color: var(--text); }
.hero__sub { margin-top: var(--s3); font-size: 13px; color: var(--muted); }
.hero__bob {
  margin-top: var(--s2);
  display: flex;
  align-items: center;
  gap: var(--s2);
  font-size: 13px;
  color: var(--lamp);
}

/* LEGEND */
.legend { display: flex; flex-wrap: wrap; gap: var(--s2) var(--s5); }
.legend__item { display: flex; align-items: center; gap: var(--s2); font-size: 12px; color: var(--muted); }
.legend__item b { color: var(--text); font-weight: 500; }
.legend__item.is-empty b { color: var(--dim); }
.swatch { width: 12px; height: 12px; border-radius: 2px; flex-shrink: 0; }
.swatch--used { background: var(--used); }
.swatch--tested { background: var(--tested); }
.swatch--agent_witnessed { background: var(--raise); box-shadow: inset 0 0 0 1.5px var(--lamp); }
.swatch--unwitnessed { background: var(--raise); outline: 1.5px dashed var(--alert); outline-offset: -1.5px; }

/* CELLS */
.grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--s2);
}
@media (min-width: 720px) { .grid { grid-template-columns: repeat(auto-fill, minmax(208px, 1fr)); } }
.cell {
  position: relative;
  min-height: 72px;
  padding: var(--s3) var(--s4);
  border-radius: 3px;
  border: 1.5px solid transparent;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--s1);
  text-align: left;
  font: inherit;
  transition: transform 120ms var(--ease-out), box-shadow 150ms var(--ease-out), background-color 150ms var(--ease-out);
}
.cell__name { font-size: 13px; font-weight: 500; overflow-wrap: break-word; line-height: 1.35; }
.cell__level { font-size: 11px; opacity: 0.8; }
.cell--used { background: var(--used); color: var(--ink); }
.cell--tested { background: var(--tested); color: var(--ink); }
.cell--agent_witnessed { background: var(--raise); border-color: var(--lamp); color: var(--text); }
.cell--agent_witnessed .cell__level { color: var(--lamp); opacity: 1; }
.cell--unwitnessed { background: var(--raise); border: 1.5px dashed var(--alert); color: var(--text); }
.cell--unwitnessed .cell__level { color: var(--alert); opacity: 1; }
.cell:hover { transform: translateY(-1px); }
.cell:active { transform: scale(0.97); }
.cell[aria-pressed="true"] { box-shadow: 0 0 0 3px var(--ink), 0 0 0 4.5px var(--text); }
.cell:focus-visible { outline: 2px solid var(--lamp); outline-offset: 5px; }

/* DETAIL */
.detail {
  margin-top: var(--s4);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: var(--s5);
}
@media (min-width: 720px) { .detail { padding: var(--s6); } }
.detail__head { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--s2) var(--s4); }
.detail__name { font-size: 16px; font-weight: 500; overflow-wrap: break-word; }
.pill {
  display: inline-flex; align-items: center; gap: var(--s1);
  font-size: 11px; padding: 2px var(--s2); border-radius: 2px;
  border: 1px solid var(--line-strong); color: var(--muted);
}
.pill--agent_witnessed { color: var(--lamp); border-color: rgba(242,181,68,0.4); }
.pill--unwitnessed { color: var(--alert); border-color: rgba(224,118,90,0.4); }
.facts {
  margin-top: var(--s5);
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--s1) var(--s5);
}
@media (min-width: 720px) { .facts { grid-template-columns: max-content minmax(0, 1fr); row-gap: var(--s2); } }
.facts dt { font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); padding-top: 2px; }
.facts dd { font-size: 13px; overflow-wrap: break-word; margin-bottom: var(--s2); }
@media (min-width: 720px) { .facts dd { margin-bottom: 0; } }
.witness { margin-top: var(--s5); display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s5); }
@media (min-width: 720px) { .rules { grid-template-columns: repeat(2, minmax(0, 1fr)); column-gap: var(--s5); } }
.code {
  font-size: 12px;
  line-height: 1.7;
  background: var(--ink);
  border: 1px solid var(--line);
  border-radius: 3px;
  padding: var(--s4);
  white-space: pre;
  overflow-x: auto;
}
.rules-label { display: block; margin-bottom: var(--s3); }
.rules { list-style: none; display: grid; gap: var(--s2); font-size: 12.5px; }
.rules li { display: grid; grid-template-columns: 16px minmax(0, 1fr); gap: var(--s2); align-items: start; }
.rules .icon { width: 16px; height: 16px; margin-top: 2px; }
.rules .ok { color: var(--lamp); }
.rules .fail { color: var(--alert); }
.rules .skip { color: var(--dim); }
.rules small { display: block; color: var(--muted); font-size: 11.5px; }

/* BOB STRIP */
.steps {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  border-top: 1px solid var(--line-strong);
}
@media (min-width: 720px) { .steps { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
.step { padding: var(--s5) 0; border-bottom: 1px solid var(--line); }
@media (min-width: 720px) {
  .step { padding: var(--s5) var(--s5) var(--s5) 0; border-bottom: 0; }
  .step + .step { padding-left: var(--s5); border-left: 1px solid var(--line); }
}
.step__top { display: flex; align-items: center; gap: var(--s3); color: var(--lamp); }
.step__top .icon { width: 22px; height: 22px; }
.step__n { font-size: 11px; color: var(--muted); letter-spacing: 0.1em; }
.step__title { margin-top: var(--s3); font-size: 14px; font-weight: 500; }
.step__text { margin-top: var(--s1); font-size: 12.5px; color: var(--muted); text-wrap: pretty; }
.cost {
  margin-top: var(--s5);
  display: flex; flex-wrap: wrap; align-items: center; gap: var(--s2) var(--s5);
  font-size: 13px; color: var(--muted);
}
.cost__main { display: flex; align-items: center; gap: var(--s2); color: var(--text); }
.cost__main .icon { width: 18px; height: 18px; color: var(--lamp); }
.textlink {
  display: inline-flex; align-items: center; gap: var(--s1);
  color: var(--muted); text-decoration: underline; text-underline-offset: 3px;
  text-decoration-color: var(--dim); transition: color 150ms var(--ease-out);
}
.textlink:hover { color: var(--text); }

/* CONTEXT */
.context { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s4); }
@media (min-width: 880px) { .context { grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr); align-items: start; } }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: 3px; padding: var(--s5); min-width: 0; }
.card .eyebrow { display: block; margin-bottom: var(--s4); }
.commit { font-size: 12.5px; line-height: 1.65; white-space: pre-wrap; overflow-wrap: anywhere; font-family: inherit; }
.more { margin-top: var(--s3); }
.more summary {
  display: inline-flex; align-items: center; gap: var(--s1); cursor: pointer; list-style: none;
  font-size: 12px; color: var(--muted); text-decoration: underline; text-underline-offset: 3px;
  text-decoration-color: var(--dim);
}
.more summary::-webkit-details-marker { display: none; }
.more summary:hover { color: var(--text); }
.more summary:focus-visible { outline: 2px solid var(--lamp); outline-offset: 3px; }
.more[open] summary { margin-bottom: var(--s3); }
.counts { width: 100%; border-collapse: collapse; font-size: 13px; }
.counts th {
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted);
  font-weight: 400; text-align: right; padding: 0 0 var(--s3) var(--s3); white-space: nowrap;
}
.counts th:first-child { text-align: left; padding-left: 0; }
.counts td { padding: var(--s2) 0; border-top: 1px solid var(--line); }
.counts td + td { text-align: right; padding-left: var(--s3); width: 1%; white-space: nowrap; }
.counts .row-label { display: flex; align-items: center; gap: var(--s2); color: var(--muted); }
.counts .n0 { color: var(--dim); }
.counts .n-used { color: var(--used); }
.counts .n-tested { color: var(--tested); }
.counts .n-agent_witnessed { color: var(--lamp); }
.counts .n-unwitnessed { color: var(--alert); }
.counts tr.total td { border-top: 1px solid var(--line-strong); color: var(--text); }

/* HISTORY */
.history { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--s5) var(--s7); align-items: start; }
@media (min-width: 720px) { .history { grid-template-columns: max-content minmax(0, 1fr); } }
.history__count {
  font-family: "Bricolage Grotesque", Georgia, serif; font-weight: 700;
  font-size: clamp(56px, 8vw, 72px); line-height: 0.9; letter-spacing: -0.035em;
  font-variant-numeric: tabular-nums lining-nums; white-space: nowrap;
}
.history__count .of { color: var(--dim); }
.history__sub { margin-top: var(--s3); font-size: 13px; color: var(--muted); }
.history__facts { display: grid; gap: var(--s2); font-size: 13px; color: var(--muted); }
.history__facts b { color: var(--text); font-weight: 500; }
.history__facts .row { display: flex; align-items: flex-start; gap: var(--s2); }
.history__facts .icon { width: 16px; height: 16px; margin-top: 3px; color: var(--muted); }

/* FOOTER */
.footer {
  margin-top: var(--s8);
  padding-top: var(--s4);
  border-top: 1px solid var(--line);
  display: flex; flex-wrap: wrap; justify-content: space-between; gap: var(--s2) var(--s5);
  font-size: 12px; color: var(--muted);
}

/* MOTION */
@media (prefers-reduced-motion: no-preference) {
  /* The entrance animates `translate`, hover and press use `transform`: they compose
     instead of fighting, so hovering never restarts the entrance. */
  @keyframes rise { from { opacity: 0; translate: 0 6px; } to { opacity: 1; translate: 0 0; } }
  .block { animation: rise 250ms var(--ease-out) both; animation-delay: calc(var(--i, 0) * 60ms); }
  .cell { animation: rise 220ms var(--ease-out) both; animation-delay: calc(240ms + var(--stagger, 0) * 30ms); }
}
@media (prefers-reduced-motion: reduce) {
  .cell, .meta-link, .textlink { transition: none; }
  .cell:hover { transform: none; }
}
"""
