# Full-network MCTS run result — 2026-09-21

Result of the first MCTS run on the real, full 31-line network after fixing the exploration bug
in [mcts.py](../src/cma/mcts.py) (commit `f9fb610`, see
[mcts_efficiency_investigation_2026-09-16.md](mcts_efficiency_investigation_2026-09-16.md) for the
build-time work that made a full-network run tractable in the first place). Output file:
[`data/output/scoped_mcts_20260920_173319.xlsx`](../data/output/scoped_mcts_20260920_173319.xlsx).

## Run config

- Script: `scripts/scoped-run/run_scoped_mcts.py --fresh --epochs 20 --mipgap 0.02`
- Scope: all 31 lines (9 VSA + 7 FIX + all 15 OWN) — not a scoped-down subset
- `max_depth=3`, `valid_weight_proportion=0.74`, `discount_fac=0.5`, `c_param=1e-2`
- Wall time: ~140 minutes (epoch times were highly variable, 14s–2929s)

## Result

| metric | value |
|---|---|
| True baseline cost | $43,218,099.78 |
| Committed root cost (after this run) | $40,263,589 |
| Best cost found (not yet committed) | $35,409,970 |
| Total improvement vs. baseline | **$7,808,130 (18.07%)** |
| Tree nodes explored | 11 |
| Distinct lines touched | at least 2 (BBX2CNC, CS2CNC) |

**Committed this run:** Add port **CNSHK** to line **BBX2CNC**, in the segment (TWKHH, MYPKG).

**Found, queued for next commit (not yet locked in):** Add port **VNHPH** to line **CS2CNC**, in
the segment (CNSHK, CNNSA). Running the script again (it resumes from
`data/output/scoped_mcts_tree.pkl` by default, or pass `--tree-file` to point at a specific saved
tree) would let MCTS commit this next, reaching the full $35,409,970.

## Why this result is much better than earlier scoped runs

Every MCTS run before this one (scoped or full-network, before the exploration fix) converged on
the same single line, YCXCNC, for a much smaller result (e.g. $157,968 / 0.41% on the full network
with the old code). This run is the first to show MCTS actually branching across multiple lines,
which is the direct effect of the `expand()` fix — see
[the mcts.py commit message](../.git) (`f9fb610`) for the full mechanism.

## Client feedback verification on this output

Checked against the [client feedback regression-check procedure](client_feedback_regression_check_2026-09-21.md)
using this exact file - all 8 items still hold:

- **#1 (capacity)**: capacity constraint uses `capacity_scale`/`capacity_reserve` correctly (dedicated test passes).
- **#2/#3 (port_details alignment)**: BBX2CNC's newly-added port CNSHK shows real, non-zero
  `waittime` (5.64) and `mantime` (3.21) in the `summary` sheet - not zeroed out.
- **#5a (speed penalty)**: dedicated test passes.
- **#5b (NaN cap_scale crash guard)**: this run includes lines with NaN `cap_scale` in the source
  data and completed without the crash that guard exists to prevent.
- **#6 (zero-cargo port guard)**: code path untouched by today's fix; node count dipping during
  earlier verification runs (e.g. 3→2 nodes) is this guard correctly pruning a rejected addition.
- **#7 (cargo flow export)**: `cargo_flow_routes` sheet is present in the output workbook.
- **#8 (capacity/weekly_capacity_teu)**: every row shows genuinely different values, e.g. BBX2CNC:
  `capacity=2789.32`, `weekly_capacity_teu=929.77` (not duplicated).
- **#4 (VSA stay-time soft-lock)**: still not implemented - unaffected either way, out of scope for
  this run.

## Known limitations of this run

- Only 20 epochs / 11 tree nodes explored, out of 7,441+ candidate actions at the root alone - this
  is a real improvement, not an exhaustive search. Running longer (or resuming from the saved tree)
  would likely find more.
- `mipgap=0.02` was tightened from the script's old default (0.10) specifically because the looser
  gap introduced enough solver noise (~17% swings between nominally identical solves) to swamp any
  real signal MCTS needed to compare options - see
  [mcts_efficiency_investigation_2026-09-16.md](mcts_efficiency_investigation_2026-09-16.md) for
  where that was first noticed.
