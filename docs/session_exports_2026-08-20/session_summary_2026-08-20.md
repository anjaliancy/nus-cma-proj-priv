# Session Summary — 2026-08-20

Continuation of the client-feedback fix work from 2026-08-11. Full commit history is the
source of truth for exact code changes; this doc is for picking the thread back up.

## Fixed and pushed this session (branch `reorg-structure`)

All pushed to `origin/reorg-structure`. Commit order:

1. **`1924160`** — Add optional Singapore transshipment-share rule. *Not written this
   session* — found bundled uncommitted in `servicegraph.py` while trying to commit
   today's capacity fix; committed separately so it wasn't misattributed. A pre-existing
   (off-by-default) feature: SGSIN transshipment share vs SGSIN/MYPKG/IDJKT.
2. **`2066ace`** — Fix BBX2/BBX3 capacity constraint (client feedback **#1**) + wire up
   shift/swap MCTS actions (see below).
3. **`217f44a`** — Fix capacity/weekly_capacity_teu duplicate columns (client feedback
   **#8** — this was already fixed 2026-08-11 but never committed) + a baseline-vs-
   optimised change-summary sheet feature. *Also not written this session* — same
   "found bundled uncommitted, split out, committed accurately" situation as #1 above.
4. **`2f4abbd`** — Export cargo flow routing (client feedback **#7**).
5. **`bdff4ed`** — Fix speed soft-cap penalty miscalibration (client feedback **#5a**) +
   rewrite `tests/test_speed_penalty.py` to actually test the real code.

**Pattern worth knowing for next time:** three separate times this session, files I
needed to touch (`servicegraph.py`, `output_summary.py`) already had *other* uncommitted
work sitting in them from earlier sessions. Each time, I reverse-applied my own diff
(via `git apply -R`) to isolate and commit the pre-existing work first, then re-applied
mine as a separate commit — so no commit message misrepresents what it contains. If
`git status` shows a file already modified before you've touched it this session, check
`git diff` for that file before committing anything in it.

### #1 — BBX2/BBX3 capacity (`servicegraph.py`, `data_reader.py`, `serviceline.py`)

Root cause: the flow-capacity constraint used a flat per-vessel-rank nominal number for
every line, ignoring each proforma line's own `cap_scale` (a derating factor —
`cap_nom × cap_scale == cap_eff` in the proforma data, confirmed exactly for both BBX2
and BBX3) and `cap_reserve` (TEU reserved for external slotters — BBX2's 735 matches the
client's own stated number exactly).

BBX2/BBX3 are `svc_type = OWN`, not `VSA` — their vessel rank being reassignable by MCTS
is *correct*, confirmed directly with Anjali. Only the capacity math was wrong.

Fix: `line_capacity = (picked vessel's nominal capacity) × line.capacity_scale −
line.capacity_reserve`, applied both in the constraint and in the output-reporting
capacity numbers.

**Known open assumption**, flagged in code comments: if MCTS reassigns a line to a
different vessel rank, the fix still applies that line's *original* proforma
`cap_scale`/`cap_reserve` to the new vessel — treated as fixed per-line values, not
something that scales with vessel size. Not confirmed with the client.

### Shift/swap MCTS action-space gap (not a numbered client-feedback item)

Cross-checked the MCTS spec's 7 allowed action types against what the code actually
generates. Found only 4 of 7 were reachable: add-port (one of two spec'd variants),
remove-port, and vessel-rank/speed/duration changes (which aren't MCTS moves at all —
they're MILP variables re-solved per topology, not tree actions).

`shift_port()`/`swap_ports()` (`serviceline.py`) were fully-implemented, working methods
— added Dec 2025 by Darrell, in a commit whose own message says "...to add the new
constraints (**incomplete**)" — but never wired into `get_feasible_actions()`
(`servicegraph.py:404`), so MCTS could never choose them. Wired them in; verified 820
valid shift moves and 200 valid swap moves are now discoverable across the real network.

**Not done:** the "Option 2" add-port variant (A→B→C → A→B→X→B→C, a revisit/loop
insert) is still unimplemented — only "Option 1" (A→B→X→C) exists.

**Performance note, not yet tuned:** generating shift/swap candidates is O(n²) per line
(n = ports on that line), each candidate building+validating a new `ServiceLine`. Real
added cost per MCTS tree node, not yet measured at scale.

### #7 — Cargo flow routing export (`servicegraph.py`, `output_summary.py`)

Solver already computed full per-flow, per-path routing internally; it just was never
decoded into a readable form or written to the output workbook. Added a
`cargo_flow_routes` list to the solution dict and a new `cargo_flow_routes` sheet in the
output Excel workbook.

Verified with a reduced-scope real-data solve (small OD-pair subset, full network of
lines/ports still loaded) that routes with nonzero flow populate correctly. **A true
full-network end-to-end verification is still pending** — see "known unresolved issue"
below.

### #5a — Speed soft-cap penalty miscalibration (`servicegraph.py`)

`cap_index = ceil(speed_soft_cap - speed_level0)` assumed a 1kt step between speed
levels; the real fleet grid steps in 0.5kt increments. Result: the ×2 fuel penalty was
starting at 13.5kt instead of the intended 17.0kt (first level above the 16.5kt
threshold) — the penalized zone was roughly twice as wide as the spec calls for.

Fix is *not* simply "divide by the step size" — the client-feedback doc's own suggested
fix formula (`ceil((cap - level0) / step)`) still gets the exact-boundary case wrong: 16.5
lands exactly on a grid point, and plain `ceil` doesn't move past an exact match, so it
resolves to 16.5 itself rather than 17.0. Used `floor(...) + 1` instead, which correctly
lands on the first level *strictly above* the cap in every case, including this one.

Extracted the formula into `compute_speed_penalty_cap_index()` (module-level function in
`servicegraph.py`) so there's exactly one implementation.

**Also fixed:** `tests/test_speed_penalty.py` previously re-typed its own copy of the
buggy formula in every test and checked it against a fabricated 1kt-step speed array
instead of the real fleet's 0.5kt-step grid — meaning it never actually exercised the
production code and could not have caught this bug, or would not catch a regression of
it. Rewrote the whole file to import and call the real function against the real speed
grid (`vessel_pool.get_speed_levels()`). All 13 tests pass and now provide real coverage.

## New findings this session, not yet acted on

### FIX-line freeze gap (real bug, found via spec review)

`proforma_CNC.csv`'s `svc_type` has **3** values, not 2: `OWN` (126 rows), `VSA` (57
rows), and **`FIX` (20 rows, 8 distinct lines: `BBXCNC, IDBLWCNC, LCXP2CNC, LCXPCNC,
LVMXCNC, SGS2CNC, SGSCNC, SP8CNC`)**. Per the spec Anjali provided:

- `VSA` — not fully CNC-operated; cargo can be rerouted onto/off it, otherwise immutable
  (no optimisation of speed/port rotation/vessel size).
- `FIX` — fully CNC-operated but highly specialised; **port rotation is fixed**, but
  speed/vessel size/cargo routing optimisation are all allowed.
- `OWN` — everything optimisable.

The freeze code (`data_reader.py:751`, `if service_type == 'VSA':`) only checks for
`'VSA'`. It has never checked for `'FIX'`. Those 8 lines currently have **zero**
protection — MCTS can freely add/delete ports, reassign rank, and change weeks on them,
same as any `OWN` line, even though their rotation should be locked.

**Why the obvious fix is wrong:** just adding `'FIX'` to the same `if service_type ==
'VSA':` block would over-lock them — that block also pins rank and weeks
(`servicegraph.py:955-965`, `:981`), which FIX lines are explicitly allowed to have
optimised. `line.frozen` currently conflates two different things (topology-lock,
rank/weeks-lock) that need to split into two separate flags: one for topology-only
(true for both VSA and FIX), one for rank/weeks (true for VSA only). **Not implemented
yet.**

### VSA slot-fee cost gap (data gap, not a code bug)

Checked what CMA actually pays for using VSA capacity in the model. Confirmed via code
(`servicegraph.py:1092-1099`): chartering, bunkering, and port-call costs are correctly
excluded for VSA lines (the partner owns the ship). But **transshipment cost is not
excluded** — it's charged for every line including VSA, and it's directly computed from
stay time. This means MCTS currently has a real financial incentive to shrink a VSA
line's stay time below what the partner actually operates at, since doing so lowers this
cost term — not just a cosmetic drift, an actively exploitable one.

There's an existing `TODO(slot-fee)` comment in the code (`servicegraph.py:1097`) noting
CMA presumably pays the partner some per-slot/per-TEU fee that isn't modeled at all.
Checked both the data files and the project's own spec document
(`data/input/Documentation/Network Optimisation Documentation.docx` — not previously
digitized/searched in this repo) — **no such pricing data exists anywhere**. This is a
genuine missing input, not something fixable in code alone; would need a number from the
client if it matters for their cost comparisons.

Considered and rejected: excluding VSA transshipment cost too (to remove the incentive
without needing a stay-time lock). Rejected because it would make VSA capacity look
completely free to the model, which would bias MCTS toward over-using VSA lines
regardless of real cost — a bigger distortion than the one it would fix, and it doesn't
address the client's actual complaint (schedule realism), just the cost side.

## Still open / paused

- **#4 — VSA stay-time lock.** Paused mid-implementation. Direction agreed: a **soft/
  penalized** lock (slack variable + objective penalty, same pattern as the Singapore
  transshipment-share rule already in the codebase), *not* a hard equality — a hard lock
  risks the same infeasibility failure mode already documented for the VSA speed lock
  (`data_reader.py:730-735`): distance/time constraints already imply a stay-time value
  from other locked things, and a hard-equality pin can contradict the *separate*
  minimum-stay-time-for-cargo-volume constraint. **Not implemented.**
- **#2/#3** — `output_summary.py`'s `port_details` misalignment after MCTS adds a port
  to a line. Not looked at this session.
- **#6** — no MCTS guard against adding a zero-cargo port. Confirmed still needs a
  change inside the core search loop; not attempted.
- **FIX-line freeze split** — see above, real bug, not yet implemented.
- **Shift/swap "Option 2" add-port variant** — not implemented.
- **Shift/swap performance tuning** — O(n²) candidate generation per line, not measured
  at MCTS-tree scale yet.

## Known unresolved issue: full-network solve is very slow

Tried running the full 31-line, 182-port, 741-OD-pair network (via
`scripts/run_full_mcts.py`) twice this session to verify fixes end-to-end. Both times it
got stuck for 2+ hours on `"Solving baseline (root)..."` before being manually killed.
Confirmed via CPU usage (~97% utilization the whole time) that it's not hung — it's
genuinely spending that long in cvxpy's *problem-construction* step (visible warning at
startup: `"Objective contains too many subexpressions. Consider vectorizing your CVXPY
code"`), which isn't bounded by `solver-TimeLimit` (that only bounds Gurobi's own solve
time, not building the problem).

This is a **pre-existing performance issue**, unrelated to any fix made this session —
confirmed by testing with only a handful of OD pairs (network of lines/ports unchanged),
which solved in ~53s, meaning OD-pair count is a major driver of the slowdown, separate
from line/port count. Not investigated further; worth a dedicated session if it's
blocking full-network validation going forward.
