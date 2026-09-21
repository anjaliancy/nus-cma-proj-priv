# Pre-MCTS-fix outputs — kept for reference only

These 5 files are all from **before** the MCTS exploration bug was fixed in commit `f9fb610`
(2026-09-21). Don't use them as a baseline or reference for current work — see
[scoped_mcts_run_result_2026-09-21.md](../../../docs/scoped_mcts_run_result_2026-09-21.md) for the
current best output instead (`data/output/scoped_mcts_20260920_173319.xlsx`).

## Why the old files look so different

Before the fix, `expand()` scored never-tried actions with a random guess and compared that guess
directly against already-explored actions' real values. Since every untried candidate shared the
same base guess, whichever one "won" came down to random noise, not a genuine comparison — so MCTS
almost always got stuck on whichever action got lucky early and rarely explored anything else. In
practice, every run before the fix converged on the same single line, YCXCNC, no matter the network
scope or hyperparameters.

Result: these runs found only a tiny, repetitive improvement ($157,968 / 0.41% on the full network)
versus $7,808,130 (18.07%) across multiple lines after the fix. If you compare numbers from these
files against a current run, they will look wrong — they're not wrong, they're just from the
broken search.

## The files

- `scoped_baseline_20260916_080017.xlsx` — a scoped-subset baseline solve, pre-fix.
- `scoped_mcts_20260917_124119.xlsx`, `scoped_mcts_20260917_132510.xlsx`,
  `scoped_mcts_20260917_140429.xlsx` — scoped-subset MCTS runs, pre-fix.
- `scoped_mcts_tree.pkl` — the saved search tree from those pre-fix runs. Also affected by the
  separate (still-open) resume-crash bug documented in commit `24cff31`, so don't try to resume
  search from it.
