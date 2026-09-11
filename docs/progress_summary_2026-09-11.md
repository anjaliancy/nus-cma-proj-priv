# Progress summary — client feedback, fixes, and visualisation

_Written 2026-09-11. Plain-language recap of what's been worked on, for anyone
picking this project up without the full session history. Each item is
bug → fix → why it matters._

---

## 1. Client feedback (8 items from the full-scope MCTS review)

Full detail and root-cause tracing: [client_feedback_2026-08-04.md](client_feedback_2026-08-04.md),
[client_feedback_error_attribution_2026-08-11.md](client_feedback_error_attribution_2026-08-11.md),
[client_feedback_response_2026-08-23.md](client_feedback_response_2026-08-23.md).

| # | Issue | Status |
|---|---|---|
| 1 | BBX2/BBX3 vessel capacity didn't match the client's own numbers | ✅ Fixed — `cap_scale`/`cap_reserve` wired into the capacity constraint |
| 2/3 | BMX wait/manoeuvring times showed as 0 after a port was added | ✅ Fixed — ports were matched to proforma data by list position, not port ID; broke as soon as a line had one more port than proforma |
| 4 | VSA (partner) lines drift even though they're supposed to be frozen | ⏳ Open — topology/schedule/vessel-type locking confirmed correct; port stay times still need a soft/penalised lock (a hard lock risks infeasibility) |
| 5a | BBX sails at 19kt despite a 16.5kt soft speed cap | ✅ Fixed — the penalty was starting at 13.5kt instead of 17.0kt (a step-size bug); extracted into one function, test suite rewritten (it was never testing the real code) |
| 5b | Why BBX still rides 19kt even after 5a | ⏳ Narrowed, still open — not a bug in BBX's own line economics; looks like a network-wide interaction (cargo transshipping through BBX from other lines) that only shows up solved together with the rest of the network |
| 6 | Ports with zero cargo benefit (CNCWN, MYLBU) were still being added | ✅ Fixed — MCTS now rejects a port addition if the solved network routes ~0 cargo through it, and won't re-offer that exact move |
| 7 | Cargo flow routing wasn't visible in the output | ✅ Fixed — new `cargo_flow_routes` sheet in the output workbook |
| 8 | `capacity` vs `weekly_capacity_teu` showed identical values; `vrank_mix` needed explaining | ✅ Fixed/clarified — duplicate-column export bug fixed; `vrank_mix` documented (e.g. "5:2;6:1" = 2 vessels of type 5, 1 of type 6) |

**Also found and fixed along the way, not originally numbered:**
- A NaN in `cap_scale`/`cap_reserve` was crashing the solver outright for some VSA lines (surfaced while investigating #5b).
- `svc_type` has a third value, `FIX` (8 lines), that the freeze code never checked — only `'VSA'` — so those 8 lines had **zero** protection (topology could drift). Fixed by splitting "frozen" into a topology-only flag (VSA + FIX) and a separate rank/weeks flag (VSA only), so FIX lines stay optimisable on rank/speed/weeks as intended.

## 2. VSA implied-speed mismatch (found after the numbered items, fixed 2026-09-10/11)

Separate from #4/#5 above. VSA lines' *implied* sailing speed (distance ÷ sailing
time from the solved network) was running 10–27% below their published speed.
Two independent causes, both needed fixing — see
[vsa_speed_stay_investigation_2026-09-09.md](vsa_speed_stay_investigation_2026-09-09.md)
and [vsa_progress_2026-09-10.md](vsa_progress_2026-09-10.md) for the full trail:

1. The sailing-days formula only subtracted **stay** time from the weekly cycle,
   so waiting + manoeuvring hours were silently counted as sailing time too —
   inflating sailing days and deflating implied speed.
2. Once VSA speed was unlocked from the schedule (an earlier, deliberate fix —
   locking it caused solver infeasibility), nothing pinned VSA sailing days
   either, so the solver picked an arbitrary value. Fixed with a hard **lower
   bound** on VSA stay-days (not a hard equality, so it can't cause the same
   infeasibility risk).

**Result:** 8 of 9 VSA lines now match published speed within ~0.3%. The 2
that don't are a rounding-boundary case and one bad data cell in the source
proforma file — both investigated and parked as non-model issues.

**Why it matters:** VSA lines are partner-operated capacity CMA doesn't
control the economics of, so the model needs to trust their published
schedule rather than silently re-optimise around a wrong implied speed.

## 3. Visualisation rebuild

Client review feedback on an earlier MCTS search-tree visualisation: it would
be more useful if it showed **which port was explored at each branch** (like a
chess minimax tree labelling each move). That visualisation had been built as
a claude.ai Artifact and the link was lost, so it was rebuilt from scratch
using the same underlying data (`tuning_results/*_nodes.csv`).

- A first pass added the branch labels to the existing Streamlit dashboard's
  tree view — turned out not to be the one being asked about.
- The actual target was a standalone interactive page with three views:
  **search tree** (every branch labelled with the port added/removed, the
  segment, and the line — the client's ask), **replay** (an epoch slider that
  regrows the tree), and **waterfall** (the best path's real marginal
  weekly-cost changes, step by step).
- Rebuilt as `scripts/build_mcts_viz.py`, which generates
  `docs/mcts_search_tree.html` (self-contained, no Streamlit/chart library —
  works offline and as a shareable claude.ai Artifact).
- The old Streamlit dashboard (`scripts/dashboard.py`) was removed entirely;
  this is now the only search-tree visualisation in the project.

## 4. Still open

- **#4** — VSA stay-time soft lock (direction agreed, not implemented).
- **#5b** — why BBX rides 19kt in the full network (narrowed to a network-wide
  interaction, not yet root-caused).
- **#6 full verification** — the zero-cargo-port rejection is verified piece
  by piece, but an end-to-end full-network MCTS run to confirm it in practice
  is still pending (blocked by the full-network solve performance issue,
  below).
- **Full 31-line/182-port network is too slow to solve end-to-end for
  verification** (2+ hrs, stuck in problem construction, not the Gurobi solve
  itself) — pre-existing, not yet investigated.
- **VSA slot-fee gap** — VSA capacity's real per-slot cost to CMA isn't
  modelled anywhere; confirmed as a genuine missing input, not a code bug.
- **Numerical conditioning** — Big-M values (1e7–2e9) vs. real costs (~$22/day)
  can cause "optimal" solves that leave money on the table; flagged, not
  investigated.
