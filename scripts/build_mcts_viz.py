"""Build a self-contained HTML visualisation of one MCTS search tree.

Reads a ``full_mcts_<timestamp>_nodes.csv`` (one row per search-tree node, see
``docs/visualisation.md``) and writes a single HTML file with three views:

  1. Search tree  - node-link tree; every branch is labelled with the port MCTS
     added / removed at that step and the segment + line it belongs to.
  2. Replay       - the same tree with an epoch slider that regrows it.
  3. Waterfall    - the best root->leaf path as marginal weekly-cost changes.

All geometry is computed here and baked into the file as JSON; the page's own
JavaScript only emits SVG and handles the slider, so it works offline and as a
claude.ai Artifact (no network, no chart library).

Usage:
    .venv\\Scripts\\python.exe scripts\\build_mcts_viz.py \\
        [--nodes tuning_results/full_mcts_20260708_203156_nodes.csv] \\
        [--out docs/mcts_search_tree.html]
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_NODES = ROOT / 'tuning_results' / 'full_mcts_20260708_203156_nodes.csv'
DEFAULT_OUT = ROOT / 'docs' / 'mcts_search_tree.html'

# UN/LOCODE -> readable name, only for ports we are confident about. Anything not
# here just shows as its code (which is what the search data speaks in anyway).
PORT_NAMES = {
    'JPYOK': 'Yokohama', 'JPOSA': 'Osaka', 'JPTYO': 'Tokyo', 'JPUKB': 'Kobe',
    'JPNGO': 'Nagoya', 'CNCWN': 'Chiwan', 'CNSHK': 'Shekou', 'CNNSA': 'Nansha',
    'CNSHA': 'Shanghai', 'CNNGB': 'Ningbo', 'CNTAO': 'Qingdao', 'CNXMN': 'Xiamen',
    'CNDLC': 'Dalian', 'CNTXG': 'Tianjin', 'CNSWA': 'Shantou', 'HKHKG': 'Hong Kong',
    'KRPUS': 'Busan', 'KRUSN': 'Ulsan', 'TWKHH': 'Kaohsiung', 'TWTXG': 'Taichung',
    'MYPKG': 'Port Klang', 'MYLBU': 'Labuan', 'SGSIN': 'Singapore',
    'PHMNL': 'Manila', 'PHDVO': 'Davao', 'PHCEB': 'Cebu', 'PHBTG': 'Batangas',
    'PHCGY': 'Cagayan de Oro', 'PHSFS': 'Subic Bay', 'THBKK': 'Bangkok',
    'THLCH': 'Laem Chabang', 'VNVUT': 'Vung Tau', 'VNHPH': 'Haiphong',
    'KHKOS': 'Sihanoukville', 'MMRGN': 'Yangon', 'IDJKT': 'Jakarta',
    'IDSRG': 'Semarang', 'IDSUB': 'Surabaya',
}


def parse_action(action: str) -> dict:
    """Pull the branch decision out of a node's action string.

    '... For the #3 line 'BMXCNC -- [...]', Add Port 'JPYOK' in the segment
    (CNTAO, CNXMN).'  ->  verb/port/line_no/line_code/seg fields.
    """
    out: dict = {'verb': None, 'port': None, 'line_no': None,
                 'line_code': None, 'seg': None}
    if not action or str(action).startswith('baseline'):
        return out
    m = re.search(r"(Add|Delete) Port '([A-Z0-9]+)'", action)
    if m:
        out['verb'], out['port'] = m.groups()
    m = re.search(r"#(\d+) line '([A-Z0-9]+)", action)
    if m:
        out['line_no'], out['line_code'] = m.groups()
    m = re.search(r"segment \(([A-Z0-9]+),\s*([A-Z0-9]+)\)", action)
    if m:
        out['seg'] = list(m.groups())
    return out


def child_index(node_id: str) -> int:
    return int(node_id.rsplit('.', 1)[-1]) if '.' in node_id else 0


def layout(df: pd.DataFrame) -> dict[str, float]:
    """Tidy left-to-right tree: y-slot per node (leaves stacked, parents centred
    over their children). Depth gives the x column later."""
    kids: dict[str, list[str]] = {}
    for nid, pid in zip(df['node_id'], df['parent_id']):
        kids.setdefault(pid, []).append(nid)
    for v in kids.values():
        v.sort(key=child_index)

    yslot: dict[str, float] = {}
    nxt = [0.0]

    def assign(nid: str) -> float:
        ch = kids.get(nid, [])
        if not ch:
            yslot[nid] = nxt[0]
            nxt[0] += 1.0
        else:
            yslot[nid] = sum(assign(c) for c in ch) / len(ch)
        return yslot[nid]

    root = df.loc[df['parent_id'] == '', 'node_id'].iloc[0]
    assign(root)
    return yslot


def build_data(nodes_csv: Path) -> dict:
    df = pd.read_csv(nodes_csv)
    df['parent_id'] = df['parent_id'].fillna('')
    df['node_id'] = df['node_id'].astype(str)
    df['parent_id'] = df['parent_id'].astype(str).replace('nan', '')

    finite = df[df['cost'].notna() & (df['cost'] != float('inf'))]
    baseline = float(df.loc[df['depth'] == 0, 'cost'].iloc[0])
    best_row = finite.loc[finite['cost'].idxmin()]
    best_id = str(best_row['node_id'])
    best_cost = float(best_row['cost'])

    parts = best_id.split('.')
    best_path = ['.'.join(parts[:i + 1]) for i in range(len(parts))]
    best_set = set(best_path)

    yslot = layout(df)
    max_depth = int(df['depth'].max())
    max_visits = int(df['visits'].max())
    max_epoch = int(df['epoch_first_seen'].max())

    by_id = df.set_index('node_id')
    nodes = []
    for _, r in df.iterrows():
        nid = str(r['node_id'])
        cost = float(r['cost']) if pd.notna(r['cost']) else None
        a = parse_action(r['action'])
        nodes.append({
            'id': nid,
            'parent': r['parent_id'],
            'depth': int(r['depth']),
            'yslot': yslot[nid],
            'cost': cost,
            'dev': None if cost is None else (cost - baseline) / baseline,
            'visits': int(r['visits']),
            'epoch': int(r['epoch_first_seen']),
            'on_best': nid in best_set,
            'is_root': r['parent_id'] == '',
            'port': a['port'],
            'port_name': PORT_NAMES.get(a['port'] or ''),
            'verb': a['verb'],
            'line_no': a['line_no'],
            'line_code': a['line_code'],
            'seg': a['seg'],
        })

    # Waterfall: marginal weekly-cost change along the best path.
    steps = []
    for i in range(1, len(best_path)):
        nid = best_path[i]
        r = by_id.loc[nid]
        a = parse_action(r['action'])
        prev_cost = float(by_id.loc[best_path[i - 1], 'cost'])
        cur_cost = float(r['cost'])
        steps.append({
            'label': f"{'+' if a['verb'] == 'Add' else '-'} {a['port']}",
            'sub': f"#{a['line_no']} {a['line_code']}",
            'from': prev_cost,
            'to': cur_cost,
            'delta': cur_cost - prev_cost,
        })

    return {
        'meta': {
            'source': nodes_csv.name,
            'baseline': baseline,
            'best_cost': best_cost,
            'saving': baseline - best_cost,
            'saving_pct': (baseline - best_cost) / baseline * 100,
            'max_depth': max_depth,
            'max_visits': max_visits,
            'max_epoch': max_epoch,
            'n_nodes': len(df),
            'best_epoch': int(by_id.loc[best_id, 'epoch_first_seen']),
        },
        'nodes': nodes,
        'best_path': best_path,
        'waterfall': steps,
    }


# --------------------------------------------------------------------------- HTML

def render_html(data: dict, artifact: bool = False) -> str:
    payload = json.dumps(data, separators=(',', ':'))
    m = data['meta']
    subtitle = (
        f"Full network - 31 service lines, 182 ports, 741 OD demands - "
        f"{m['n_nodes']} candidate networks solved. "
        f"Baseline ${m['baseline'] / 1e6:,.2f}M/week - "
        f"best ${m['best_cost'] / 1e6:,.2f}M/week "
        f"(-{m['saving_pct']:.1f}%, -${m['saving'] / 1e6:,.2f}M). "
        f"Reward = 1 / weekly cost, so lower is better."
    )
    head = f"""<title>MCTS Search Tree</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Spectral:wght@500;600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --ground:   #f6f7f7;
    --surface:  #ffffff;
    --surface-2:#eef1f1;
    --ink:      #12232e;
    --ink-soft: #35474f;
    --muted:    #63747c;
    --hair:     #dfe4e3;
    --accent:   #0a6c8f;
    --accent-ink:#ffffff;
    --good:     #1f7a52;
    --good-soft:#dbeee3;
    --bad:      #b0472c;
    --bad-soft: #f2e0d9;
    --neutral:  #9aa7ab;
    --shadow:   0 1px 2px rgba(18,35,46,.06), 0 8px 24px rgba(18,35,46,.06);
  }}
  :root:not([data-theme="light"]) {{
    @media (prefers-color-scheme: dark) {{
      --ground:   #0e181d;
      --surface:  #15242c;
      --surface-2:#1c2e37;
      --ink:      #e9edec;
      --ink-soft: #c2cccd;
      --muted:    #8fa0a5;
      --hair:     #26363e;
      --accent:   #47b2d6;
      --accent-ink:#07222c;
      --good:     #58c58c;
      --good-soft:#173a2b;
      --bad:      #e08b6f;
      --bad-soft: #3a241c;
      --neutral:  #6b7a80;
      --shadow:   0 1px 2px rgba(0,0,0,.3), 0 10px 30px rgba(0,0,0,.35);
    }}
  }}
  :root[data-theme="dark"] {{
    --ground:   #0e181d;
    --surface:  #15242c;
    --surface-2:#1c2e37;
    --ink:      #e9edec;
    --ink-soft: #c2cccd;
    --muted:    #8fa0a5;
    --hair:     #26363e;
    --accent:   #47b2d6;
    --accent-ink:#07222c;
    --good:     #58c58c;
    --good-soft:#173a2b;
    --bad:      #e08b6f;
    --bad-soft: #3a241c;
    --neutral:  #6b7a80;
    --shadow:   0 1px 2px rgba(0,0,0,.3), 0 10px 30px rgba(0,0,0,.35);
  }}

  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--ground);
    color: var(--ink);
    font-family: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
    line-height: 1.55;
  }}
  .wrap {{ max-width: 1140px; margin: 0 auto; padding: 40px 24px 72px; }}

  header.page {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }}
  h1 {{
    font-family: "Spectral", Georgia, serif;
    font-weight: 600; font-size: 30px; letter-spacing: .1px;
    margin: 0 0 8px; text-wrap: balance;
  }}
  .lede {{ color: var(--muted); font-size: 14px; max-width: 68ch; margin: 0; }}
  .src {{
    font-family: "IBM Plex Mono", monospace; font-size: 11px; color: var(--muted);
    margin-top: 10px; letter-spacing: .2px;
  }}
  .theme-btn {{
    flex: none; font: inherit; font-size: 12px; color: var(--ink-soft);
    background: var(--surface); border: 1px solid var(--hair); border-radius: 999px;
    padding: 6px 14px; cursor: pointer;
  }}
  .theme-btn:hover {{ border-color: var(--accent); color: var(--accent); }}

  section {{ margin-top: 44px; }}
  .eyebrow {{
    display: inline-flex; align-items: baseline; gap: 10px;
    font-family: "IBM Plex Mono", monospace; font-size: 12px;
    text-transform: uppercase; letter-spacing: .16em; color: var(--muted);
  }}
  .eyebrow b {{ color: var(--accent); font-weight: 600; }}
  h2 {{
    font-family: "Spectral", Georgia, serif; font-weight: 600;
    font-size: 21px; margin: 8px 0 6px;
  }}
  .note {{ color: var(--muted); font-size: 13.5px; margin: 0 0 18px; max-width: 74ch; }}

  .panel {{
    background: var(--surface); border: 1px solid var(--hair);
    border-radius: 14px; box-shadow: var(--shadow); padding: 10px;
    overflow-x: auto;
  }}
  .panel svg {{ display: block; width: 100%; height: auto; min-width: 720px; }}

  .controls {{
    display: flex; align-items: center; gap: 18px; flex-wrap: wrap;
    padding: 14px 12px 4px;
  }}
  .controls label {{
    font-family: "IBM Plex Mono", monospace; font-size: 12px;
    text-transform: uppercase; letter-spacing: .12em; color: var(--muted);
  }}
  input[type="range"] {{ flex: 1; min-width: 220px; accent-color: var(--accent); }}
  .epoch-read {{
    font-family: "IBM Plex Mono", monospace; font-size: 13px; color: var(--ink-soft);
    font-variant-numeric: tabular-nums; min-width: 74px; text-align: right;
  }}
  .stats {{ display: flex; gap: 28px; flex-wrap: wrap; padding: 10px 14px 4px; }}
  .stat .k {{
    font-family: "IBM Plex Mono", monospace; font-size: 20px; font-weight: 600;
    color: var(--ink); font-variant-numeric: tabular-nums;
  }}
  .stat .l {{
    font-size: 11px; text-transform: uppercase; letter-spacing: .1em; color: var(--muted);
  }}

  .legend {{
    display: flex; gap: 20px; flex-wrap: wrap; align-items: center;
    padding: 12px 14px 2px; font-size: 12px; color: var(--muted);
  }}
  .legend span {{ display: inline-flex; align-items: center; gap: 7px; }}
  .sw {{ width: 12px; height: 12px; border-radius: 50%; flex: none; }}
  .sw.good {{ background: var(--good); }}
  .sw.bad {{ background: var(--bad); }}
  .sw.root {{ background: var(--neutral); }}
  .sw.best {{ background: transparent; border: 2.5px solid var(--accent); }}

  svg text {{ font-family: "IBM Plex Sans", sans-serif; }}
  .mono {{ font-family: "IBM Plex Mono", monospace; }}

  @media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>"""

    body = f"""<div class="wrap">
  <header class="page">
    <div>
      <h1>How the search rebuilt the network</h1>
      <p class="lede">{html.escape(subtitle)}</p>
      <p class="src">{html.escape(m['source'])}</p>
    </div>
    <button class="theme-btn" id="theme" type="button">Theme</button>
  </header>

  <section>
    <span class="eyebrow"><b>01</b> Search tree</span>
    <h2>Every branch is one port call MCTS tried</h2>
    <p class="note">
      Read left to right: each step stacks one more route edit on the baseline and
      re-solves the whole network with the MILP. The boxed label on a branch is the
      port added (<span class="mono">+</span>) or removed (<span class="mono">-</span>),
      the segment it goes into, and the line it belongs to. Node fill = weekly cost
      against the baseline (greener cheaper, redder pricier), ring = the best network
      found, size = how often the search revisited that node.
    </p>
    <div class="legend">
      <span><i class="sw root"></i> baseline</span>
      <span><i class="sw good"></i> cheaper than baseline</span>
      <span><i class="sw bad"></i> pricier than baseline</span>
      <span><i class="sw best"></i> best path</span>
    </div>
    <div class="panel"><div id="tree-full"></div></div>
  </section>

  <section>
    <span class="eyebrow"><b>02</b> Replay</span>
    <h2>Watch the tree grow, epoch by epoch</h2>
    <p class="note">
      Drag to move through the {m['max_epoch']} epochs. The baseline is solved first;
      the first improving edit lands at epoch 12, the depth-4 winner is first solved
      at epoch {m['best_epoch']}, and a second branch off the root is opened at epoch
      {m['max_epoch'] - 2}. Long flat stretches are the search confirming shallow
      options before committing deeper.
    </p>
    <div class="controls">
      <label for="epoch">Epoch</label>
      <input type="range" id="epoch" min="1" max="{m['max_epoch']}" value="{m['max_epoch']}">
      <span class="epoch-read" id="epoch-read">{m['max_epoch']} / {m['max_epoch']}</span>
    </div>
    <div class="stats">
      <div class="stat"><div class="k" id="s-nodes">-</div><div class="l">nodes solved</div></div>
      <div class="stat"><div class="k" id="s-best">-</div><div class="l">best cost so far</div></div>
      <div class="stat"><div class="k" id="s-depth">-</div><div class="l">deepest node</div></div>
    </div>
    <div class="panel"><div id="tree-replay"></div></div>
  </section>

  <section>
    <span class="eyebrow"><b>03</b> Waterfall</span>
    <h2>The winning path is not a straight line down</h2>
    <p class="note">
      The four edits on the best root-to-leaf path, each as its real marginal change
      in weekly cost (every intermediate network was actually solved). One edit even
      costs more on its own - the search keeps it because of what it unlocks two
      steps later. Net: {('-' if m['saving'] >= 0 else '+')}${abs(m['saving']) / 1e6:,.2f}M/week
      ({('-' if m['saving'] >= 0 else '+')}{abs(m['saving_pct']):.1f}%).
    </p>
    <div class="panel"><div id="waterfall"></div></div>
  </section>
</div>

<script id="data" type="application/json">{payload}</script>
<script>
(function () {{
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent);
  var NS = "http://www.w3.org/2000/svg";

  function css(v) {{ return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }}
  function money(x) {{ return "$" + (x / 1e6).toFixed(2) + "M"; }}
  function el(tag, attrs, text) {{
    var n = document.createElementNS(NS, tag);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (text != null) n.textContent = text;
    return n;
  }}

  // ---- geometry -----------------------------------------------------------
  var M = {{ l: 76, r: 156, t: 58, b: 46 }};
  var W = 1080;
  var maxDepth = DATA.meta.max_depth;
  var maxSlot = 0;
  DATA.nodes.forEach(function (n) {{ if (n.yslot > maxSlot) maxSlot = n.yslot; }});
  var colW = (W - M.l - M.r) / Math.max(maxDepth, 1);
  var rowH = 122;
  var H = M.t + maxSlot * rowH + M.b;

  function px(n) {{ return M.l + n.depth * colW; }}
  function py(n) {{ return M.t + n.yslot * rowH; }}

  function radius(n) {{
    if (n.is_root) return 22;
    var f = Math.sqrt(n.visits / Math.max(DATA.meta.max_visits, 1));
    return 11 + 15 * f;
  }}

  // diverging cost colour around the baseline
  function costFill(n) {{
    if (n.is_root || n.dev == null) return css("--neutral");
    var t = Math.max(-1, Math.min(1, n.dev / 0.06));   // +/-6% saturates
    if (t < 0) return mix(css("--surface-2"), css("--good"), -t);
    return mix(css("--surface-2"), css("--bad"), t);
  }}
  function mix(a, b, t) {{
    var pa = hex(a), pb = hex(b);
    return "rgb(" + Math.round(pa[0] + (pb[0] - pa[0]) * t) + ","
                  + Math.round(pa[1] + (pb[1] - pa[1]) * t) + ","
                  + Math.round(pa[2] + (pb[2] - pa[2]) * t) + ")";
  }}
  function hex(c) {{
    c = c.trim();
    if (c[0] === "#") {{
      if (c.length === 4) c = "#" + c[1] + c[1] + c[2] + c[2] + c[3] + c[3];
      return [parseInt(c.substr(1, 2), 16), parseInt(c.substr(3, 2), 16), parseInt(c.substr(5, 2), 16)];
    }}
    var m = c.match(/[\\d.]+/g).map(Number);
    return [m[0], m[1], m[2]];
  }}

  function nodeById(id) {{
    for (var i = 0; i < DATA.nodes.length; i++) if (DATA.nodes[i].id === id) return DATA.nodes[i];
    return null;
  }}

  // ---- tree renderer ----------------------------------------------------
  function renderTree(mount, cutoff) {{
    mount.innerHTML = "";
    var svg = el("svg", {{ viewBox: "0 0 " + W + " " + H, role: "img",
      "aria-label": "MCTS search tree" }});

    var visible = DATA.nodes.filter(function (n) {{ return n.epoch <= cutoff; }});
    var vset = {{}};
    visible.forEach(function (n) {{ vset[n.id] = true; }});

    // depth guide lines + labels
    for (var d = 0; d <= maxDepth; d++) {{
      var x = M.l + d * colW;
      svg.appendChild(el("line", {{ x1: x, y1: M.t - 30, x2: x, y2: H - M.b + 8,
        stroke: css("--hair"), "stroke-width": 1, "stroke-dasharray": "2 5" }}));
      var lab = el("text", {{ x: x, y: H - M.b + 26, "text-anchor": "middle",
        "font-size": 11, fill: css("--muted") }}, d === 0 ? "baseline" : "edit " + d);
      lab.setAttribute("letter-spacing", ".08em");
      svg.appendChild(lab);
    }}

    // links + branch labels
    visible.forEach(function (n) {{
      if (!n.parent || !vset[n.parent]) return;
      var p = nodeById(n.parent);
      var x1 = px(p) + radius(p), y1 = py(p), x2 = px(n) - radius(n), y2 = py(n);
      var mx = (x1 + x2) / 2;
      var best = n.on_best && p.on_best;
      svg.appendChild(el("path", {{
        d: "M" + x1 + " " + y1 + " C " + mx + " " + y1 + ", " + mx + " " + y2 + ", " + x2 + " " + y2,
        fill: "none", stroke: best ? css("--accent") : css("--hair"),
        "stroke-width": best ? 3.5 : 1.6 }}));
      branchLabel(svg, n, (x1 + x2) / 2, (y1 + y2) / 2, best);
    }});

    // nodes
    visible.forEach(function (n) {{
      var g = el("g", {{}});
      var r = radius(n);
      g.appendChild(el("circle", {{
        cx: px(n), cy: py(n), r: r, fill: costFill(n),
        stroke: n.on_best ? css("--accent") : css("--surface"),
        "stroke-width": n.on_best ? 3 : 1.5 }}));
      if (n.is_root) {{
        var t = el("text", {{ x: px(n), y: py(n) + 4, "text-anchor": "middle",
          "font-size": 10, fill: css("--ink-soft") }}, "root");
        g.appendChild(t);
      }}
      // cost under the node
      var c = el("text", {{ x: px(n), y: py(n) + r + 16, "text-anchor": "middle",
        "font-size": 11.5, fill: css("--ink-soft") }}, n.cost == null ? "infeasible" : money(n.cost));
      c.setAttribute("font-family", '"IBM Plex Mono", monospace');
      g.appendChild(c);
      var title = el("title", {{}}, (n.is_root ? "Baseline network" :
        (n.verb + " " + n.port + (n.port_name ? " (" + n.port_name + ")" : "") +
         "  in " + (n.seg ? n.seg[0] + "->" + n.seg[1] : "?") +
         "  on line #" + n.line_no + " " + n.line_code)) +
        "\\n" + (n.cost == null ? "infeasible" : money(n.cost)) +
        " / week   ·   " + n.visits + " visits   ·   first solved epoch " + n.epoch);
      g.appendChild(title);
      svg.appendChild(g);
    }});

    mount.appendChild(svg);
  }}

  function branchLabel(svg, n, cx, cy, best) {{
    var main = (n.verb === "Add" ? "+ " : "- ") + (n.port || "?");
    var sub = (n.seg ? n.seg[0] + "\\u2192" + n.seg[1] : "") +
              (n.line_no ? "  ·  #" + n.line_no + " " + n.line_code : "");
    var wMain = 10 + main.length * 8.2;
    var wSub = sub ? 16 + sub.length * 5.6 : 0;
    var w = Math.max(wMain, wSub);
    var h = sub ? 34 : 22;
    var g = el("g", {{}});
    g.appendChild(el("rect", {{
      x: cx - w / 2, y: cy - h / 2, width: w, height: h, rx: 6,
      fill: best ? css("--accent") : css("--surface"),
      stroke: best ? css("--accent") : css("--hair"), "stroke-width": 1.4 }}));
    var t1 = el("text", {{ x: cx, y: cy + (sub ? -3 : 4), "text-anchor": "middle",
      "font-size": 12.5, "font-weight": 600,
      fill: best ? css("--accent-ink") : css("--ink") }}, main);
    t1.setAttribute("font-family", '"IBM Plex Mono", monospace');
    g.appendChild(t1);
    if (sub) {{
      var t2 = el("text", {{ x: cx, y: cy + 12, "text-anchor": "middle",
        "font-size": 9.5, fill: best ? css("--accent-ink") : css("--muted") }}, sub);
      t2.setAttribute("font-family", '"IBM Plex Mono", monospace');
      if (best) t2.setAttribute("opacity", ".85");
      g.appendChild(t2);
    }}
    svg.appendChild(g);
  }}

  // ---- replay ---------------------------------------------------------
  var slider = document.getElementById("epoch");
  var readOut = document.getElementById("epoch-read");
  var sNodes = document.getElementById("s-nodes");
  var sBest = document.getElementById("s-best");
  var sDepth = document.getElementById("s-depth");

  function updateReplay() {{
    var e = +slider.value;
    readOut.textContent = e + " / " + DATA.meta.max_epoch;
    var vis = DATA.nodes.filter(function (n) {{ return n.epoch <= e; }});
    var solved = vis.filter(function (n) {{ return n.cost != null; }});
    var best = solved.reduce(function (a, n) {{ return n.cost < a ? n.cost : a; }}, Infinity);
    var depth = vis.reduce(function (a, n) {{ return n.depth > a ? n.depth : a; }}, 0);
    sNodes.textContent = vis.length;
    sBest.textContent = isFinite(best) ? money(best) : "-";
    sDepth.textContent = "depth " + depth;
    renderTree(document.getElementById("tree-replay"), e);
  }}
  slider.addEventListener("input", updateReplay);

  // ---- waterfall ----------------------------------------------------
  function renderWaterfall() {{
    var mount = document.getElementById("waterfall");
    mount.innerHTML = "";
    var steps = DATA.waterfall;
    var wf = {{ l: 60, r: 30, t: 30, b: 70 }};
    var ww = 1080, barW = 78, gap = (ww - wf.l - wf.r - barW * (steps.length + 2)) / (steps.length + 1);
    var vals = [DATA.meta.baseline];
    steps.forEach(function (s) {{ vals.push(s.to); }});
    var lo = Math.min.apply(null, vals) * 0.985;
    var hi = Math.max.apply(null, vals) * 1.005;
    var wh = 360;
    function Y(v) {{ return wf.t + (hi - v) / (hi - lo) * (wh - wf.t - wf.b); }}

    var svg = el("svg", {{ viewBox: "0 0 " + ww + " " + wh, role: "img",
      "aria-label": "Waterfall of marginal weekly-cost changes" }});

    // gridlines
    for (var i = 0; i <= 4; i++) {{
      var gv = lo + (hi - lo) * i / 4;
      var gy = Y(gv);
      svg.appendChild(el("line", {{ x1: wf.l, y1: gy, x2: ww - wf.r, y2: gy,
        stroke: css("--hair"), "stroke-width": 1 }}));
      var gl = el("text", {{ x: wf.l - 8, y: gy + 4, "text-anchor": "end",
        "font-size": 10, fill: css("--muted") }}, "$" + (gv / 1e6).toFixed(1) + "M");
      gl.setAttribute("font-family", '"IBM Plex Mono", monospace');
      svg.appendChild(gl);
    }}

    function bar(idx, top, bot, fill, label, sub, strong) {{
      var x = wf.l + gap + idx * (barW + gap);
      svg.appendChild(el("rect", {{ x: x, y: Math.min(top, bot), width: barW,
        height: Math.max(2, Math.abs(bot - top)), rx: 3, fill: fill }}));
      var lx = x + barW / 2;
      var t1 = el("text", {{ x: lx, y: wh - wf.b + 22, "text-anchor": "middle",
        "font-size": 11.5, "font-weight": 600, fill: css("--ink") }}, label);
      t1.setAttribute("font-family", '"IBM Plex Mono", monospace');
      svg.appendChild(t1);
      if (sub) {{
        var t2 = el("text", {{ x: lx, y: wh - wf.b + 38, "text-anchor": "middle",
          "font-size": 9.5, fill: css("--muted") }}, sub);
        t2.setAttribute("font-family", '"IBM Plex Mono", monospace');
        svg.appendChild(t2);
      }}
      var vy = Math.min(top, bot) - 8;
      var vt = el("text", {{ x: lx, y: vy, "text-anchor": "middle", "font-size": 10.5,
        fill: strong ? css("--accent") : css("--ink-soft") }}, strong);
      vt.setAttribute("font-family", '"IBM Plex Mono", monospace');
      if (strong) svg.appendChild(vt);
    }}

    // baseline (full bar from axis)
    var base = DATA.meta.baseline;
    bar(0, Y(base), Y(lo), css("--neutral"), "baseline", "", money(base));
    var running = base;
    steps.forEach(function (s, i) {{
      var top = Y(Math.max(running, s.to));
      var bot = Y(Math.min(running, s.to));
      var down = s.delta < 0;
      bar(i + 1, top, bot, down ? css("--good") : css("--bad"), s.label, s.sub,
        (down ? "-" : "+") + "$" + (Math.abs(s.delta) / 1e6).toFixed(2) + "M");
      // connector
      var x0 = wf.l + gap + (i + 1) * (barW + gap);
      svg.appendChild(el("line", {{ x1: x0 - gap, y1: Y(running), x2: x0, y2: Y(running),
        stroke: css("--muted"), "stroke-width": 1, "stroke-dasharray": "3 3" }}));
      running = s.to;
    }});
    // best (full bar)
    bar(steps.length + 1, Y(running), Y(lo), css("--accent"), "best", "", money(running));

    mount.appendChild(svg);
  }}

  // ---- theme toggle -------------------------------------------------
  document.getElementById("theme").addEventListener("click", function () {{
    var cur = document.documentElement.getAttribute("data-theme");
    var next = cur === "dark" ? "light" : cur === "light" ? "dark"
      : (matchMedia("(prefers-color-scheme: dark)").matches ? "light" : "dark");
    document.documentElement.setAttribute("data-theme", next);
    redraw();
  }});

  function redraw() {{
    renderTree(document.getElementById("tree-full"), DATA.meta.max_epoch);
    updateReplay();
    renderWaterfall();
  }}
  redraw();
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", redraw);
}})();
</script>"""

    if artifact:
        return head + "\n" + body + "\n"
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        + head + "\n</head>\n<body>\n" + body + "\n</body>\n</html>\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--nodes', type=Path, default=DEFAULT_NODES)
    ap.add_argument('--out', type=Path, default=DEFAULT_OUT)
    ap.add_argument('--artifact', action='store_true',
                    help='emit without the <!doctype/html/head/body> skeleton '
                         '(for publishing as a claude.ai Artifact)')
    args = ap.parse_args()

    data = build_data(args.nodes)
    args.out.write_text(render_html(data, artifact=args.artifact), encoding='utf-8')
    m = data['meta']
    print(f'wrote {args.out}')
    print(f'  {m["n_nodes"]} nodes · baseline ${m["baseline"]/1e6:.2f}M · '
          f'best ${m["best_cost"]/1e6:.2f}M (-{m["saving_pct"]:.1f}%) · '
          f'{m["max_epoch"]} epochs')


if __name__ == '__main__':
    main()
