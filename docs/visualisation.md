# Visualising the MCTS + MILP runs

How to run the full-network model so that everything needed for visualisation is
captured, what each output file contains, and how the dashboard views map onto that
data. _Written 2026-07-08._

**Why this exists:** the weekend runs (4–5 Jul, see `FULL_RUN_RESULTS.md`) only logged
per-epoch aggregates, so the search **tree** — the most informative object in MCTS —
was thrown away. The 21% run's tree is unrecoverable. `scripts/run_full_mcts.py` now
saves the tree; every run from now on is fully visualisable.

---

## 1. How to run

From the repo root, using the project venv (the MILP needs the Gurobi WLS licence,
already configured):

```
# standard run (epochs 20, depth 3, weight 0.74) — ~30-60 min
.venv\Scripts\python.exe scripts\run_full_mcts.py

# the deep configuration that found the 21% saving — ~1-1.5 h
.venv\Scripts\python.exe scripts\run_full_mcts.py --epochs 60 --depth 4
```

Notes for a "report-ready" run:

- **Seeds are fixed** in the script (`random.seed(7)`, `np.random.seed(7)`), but MCTS
  results still vary run-to-run via solver nondeterminism and the 10% MIP gap. To
  validate across seeds, edit the two seed lines (or add a `--seed` flag) and do 2–3
  runs.
- **Baseline drift:** the root cost moves between runs because any solution within the
  10% MIP gap is accepted. For a presentation-stable baseline, tighten
  `'solver-MIPGap'` in `TP` (e.g. 0.05) — expect slower solves.
- Everything is **flushed each epoch**, so a run killed early still leaves usable files.

## 2. What gets stored (all in `tuning_results/`)

Every run writes four files sharing one timestamp `full_mcts_<YYYYMMDD_HHMMSS>`:

| File | What it is | Written |
|---|---|---|
| `….log` | Human-readable progress, one line per epoch, plus the final best-action trace | live |
| `….csv` | Per-epoch aggregates (see 2.1) | live, per epoch |
| `…_nodes.csv` | **One row per tree node** — the full search tree snapshot (see 2.2) | rewritten every epoch |
| `…_tree.pkl` | Pickle of the final `MonteCarloTree` (full objects, for ad-hoc analysis) | at the end |

### 2.1 Epoch CSV (`….csv`)

`epoch, cum_minutes, root_cost, best_cost, improvement_usd, improvement_pct,
best_depth, tree_nodes` — one row per epoch (cost curve, improvement %, time per
epoch, tree growth). Not yet consumed by the HTML page below; open it in
pandas/Excel directly if you need these.

### 2.2 Nodes CSV (`…_nodes.csv`) — the tree

One row per node in the search tree:

| Column | Meaning |
|---|---|
| `node_id` | Path-based id: root = `0`, its 2nd child = `0.1`, that node's 1st child = `0.1.0`. Stable across epochs. |
| `parent_id` | `node_id` of the parent (empty for the root). |
| `epoch_first_seen` | Epoch in which this node first appeared — enables the replay view. |
| `depth` | Number of route changes stacked on the baseline (root = 0). |
| `action` | Human-readable edit that created the node, e.g. "add TWTXG in segment CNNGB→CNSHA" (root = "baseline (no changes)"). Quoted; multi-line explanations joined with `\|`. |
| `cost` | Weekly network cost (USD) of this candidate network, from its MILP solve. |
| `visits` | MCTS visit count — how often the search returned to this branch. |
| `sum_value` | Accumulated back-propagated value (visits+value give the UCB picture). |

The file is a **snapshot rewritten each epoch**, so mid-run it always reflects the
current tree; `epoch_first_seen` preserves the growth history.

### 2.3 Tree pickle (`…_tree.pkl`)

The entire `MonteCarloTree` object (load with `MonteCarloTree.load_tree(path)`).
Use when a question isn't answerable from the CSV (e.g. inspect a candidate
network's full rotations or re-run `display_best_node`). Can be large; the CSV is
the primary interface.

## 3. Search tree / replay / waterfall

The Streamlit dashboard (`scripts/dashboard.py`) that used to live here has been
removed. Visualisation is now a single self-contained HTML page (no Streamlit, no
chart library, works offline and as a claude.ai Artifact). Build it from any run's
nodes CSV:

```
.venv\Scripts\python.exe scripts\build_mcts_viz.py \
    --nodes tuning_results/full_mcts_<timestamp>_nodes.csv
# writes docs/mcts_search_tree.html   (add --artifact for the publish-ready variant)
```

Three views on one page: **Search tree** (every branch labelled with the port
added/removed, the segment, and the line; node fill = weekly cost vs. baseline,
ring = best path, size = visits), **Replay** (epoch slider regrows the tree, with
live nodes/best-cost/depth readouts), **Waterfall** (the best root→leaf path as
real marginal weekly-cost changes). Needs a run with a `_nodes.csv` — do the run
first, the page follows.

## 4. Checklist per run (for the record / report)

1. Note the command line used (epochs / depth / weight / timelimit) — it's also in
   the first line of the `.log`.
2. After the run, confirm all four files exist and `_nodes.csv` has > 1 row.
3. Copy the final `FINAL: …` line and the best-action trace from the `.log` into
   your notes.
4. If the result is headline-worthy, repeat with 1–2 different seeds before quoting
   the number — MCTS is stochastic.

## 5. Caveats to keep in mind when presenting

- Reward = `1 / weekly cost`; all improvements are vs. that run's own root solve.
- Costs carry the MIP-gap noise (±10% tolerance per solve).
- "Add a port call" recommendations are model-level candidates — berth windows,
  contracts and transit-time promises are not modelled; frame them as options for
  operational review.
