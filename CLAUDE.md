# Project context for Claude

Read this first when starting fresh on a new machine — none of the persistent memory
from prior sessions carries over to a new computer, so this file is the handover.

## Who you're working with

Anjali is a **new RA** on this CMA CGM shipping-network optimization project. No formal
handover was given when she joined — she's building her own understanding of the
codebase from scratch. **Explain in plain language, no unexplained jargon.**

## How she likes to work

- **Explain-back learning mode** (for new concepts): introduce **one concept per
  message**, let her restate it in her own words, correct/confirm, then move on. Never
  stack multiple new ideas in one message — this has been explicitly flagged as
  overwhelming. See
  [docs/session_exports_2026-08-11/understanding end to end 10-08-2026.md](docs/session_exports_2026-08-11/understanding%20end%20to%20end%2010-08-2026.md)
  for the full running log of this teaching style in action.
- **Ground explanations in real data, not descriptions.** When walking through a data
  table or a bug, pull actual rows/values from the files or actual line numbers from the
  code — she explicitly asked for this after an abstract explanation didn't land.
- **Short explanations for bug/fix summaries.** Default to a 2-4 line version (bug → fix
  → why it matters), not tables or multi-section writeups. She's asked for shorter
  versions of the same explanation more than once — compress further than your first
  simplification pass, don't just trim slightly. Only expand if she asks for more detail.
- **Plain-language code explanations** belong in `EASY_UNDERSTAND.md` at the repo root,
  not scattered as inline comments.
- Before doing a "quick fix," verify it's actually small. One item that looked
  small from a summary turned out to need changes inside the core MCTS search loop —
  surface that complexity and ask before diving in, rather than assuming.
- No `Co-Authored-By: Claude` / AI-attribution trailers in commit messages.

## Where things stand (as of 2026-08-20)

The client (CMA CGM) reviewed the first full-scope MCTS output and flagged 8 issues —
see [docs/client_feedback_2026-08-04.md](docs/client_feedback_2026-08-04.md) for the
original feedback + investigation findings, and
[docs/session_exports_2026-08-11/client_feedback_error_attribution_2026-08-11.md](docs/session_exports_2026-08-11/client_feedback_error_attribution_2026-08-11.md)
for a table of which file/commit/author is responsible for each, and whether it was
Anjali's own code (spoiler: none of the 8 were — see that file for the one exception,
her VSA freeze fix, which was correct and intentional).
[docs/session_exports_2026-08-11/client_feedback_conversation_2026-08-11.md](docs/session_exports_2026-08-11/client_feedback_conversation_2026-08-11.md)
has the full narrative of how each issue was traced.
[docs/session_exports_2026-08-20/session_summary_2026-08-20.md](docs/session_exports_2026-08-20/session_summary_2026-08-20.md)
has the full 2026-08-20 session log (below is just the current-state summary).

**Fixed and pushed to `origin/reorg-structure`:** #1 (BBX2/BBX3 capacity — wired
`cap_scale`/`cap_reserve` into the flow-capacity constraint), #5a (speed soft-cap penalty
was starting at 13.5kt instead of 17.0kt due to a 1kt-vs-0.5kt step-size bug; fixed and
extracted into `compute_speed_penalty_cap_index()`; `tests/test_speed_penalty.py`
rewritten since it previously never tested the real code), #7 (cargo flow routing now
exported to a `cargo_flow_routes` sheet), #8 (`capacity`/`weekly_capacity_teu` dup-column
fix, committed 2026-08-20 but written 2026-08-11).

**Also fixed and pushed, not a numbered client item:** MCTS's shift/swap actions
(`shift_port`/`swap_ports` in `serviceline.py`) were fully implemented since Dec 2025 but
never wired into `get_feasible_actions()` — MCTS could only ever add/delete ports. Now
wired in and verified (820 valid shifts, 200 valid swaps found on the real network). The
spec's "Option 2" add-port variant (revisit-loop insert) is still unimplemented.

**Still open:** #2/#3 (one bug — `output_summary.py`'s `port_details` doesn't stay
aligned after MCTS adds a port to a line), #4 (VSA stay times aren't pinned — direction
agreed as a *soft/penalized* lock, not implemented yet, see session doc for why a hard
lock risks infeasibility), #6 (no MCTS guard against adding a port that moves zero cargo
— needs a change inside the core search loop, deferred as bigger than initially scoped).

**New findings from 2026-08-20, not yet fixed:** (1) `svc_type` has a third value,
`FIX` (8 lines) — spec says rotation should be locked but rank/speed/weeks stay
optimisable; the freeze code only ever checked for `'VSA'`, so these 8 lines currently
have zero protection at all. Needs splitting `line.frozen` into a topology-only flag
(VSA+FIX) and a separate rank/weeks flag (VSA only) — the naive fix of just adding `FIX`
to the existing VSA freeze block would wrongly over-lock them. (2) VSA lines' real
per-slot cost to CMA isn't modeled anywhere (confirmed via both the data files and the
project's own spec doc) — there's an existing `TODO(slot-fee)` comment flagging this;
it's a missing input, not a code bug. (3) The full 31-line/182-port network is currently
too slow to solve end-to-end for verification (2+ hrs, stuck in cvxpy problem
construction, not the Gurobi solve itself) — pre-existing, unrelated to this session's
fixes, not yet investigated.

**Also in progress, separate thread:** a data-table-by-table walkthrough (fleet, ports,
distances, demand done; existing routes / `proforma_CNC.csv` next) as part of the
explain-back learning — paused mid-table, see the "understanding end to end" doc linked
above for exactly where it left off.

## Useful technical notes

- **Gurobi**: WLS academic license configured, renews ~90 days; use `%pip` for
  `gurobipy` inside the notebook kernel.
- **Running the MILP**: the kernel is this repo's `.venv` (Python 3.12). For fast
  debugging, run the solver outside the notebook, not inside it.
- **VSA (partner) lines**: frozen lines lock topology, weeks, and vessel rank — but
  **not speed**. Locking speed too makes the MILP infeasible (hard `speed × time =
  distance` equality conflicts with the line's own schedule data) — this was a
  deliberate fix (`data_reader.py:723-735`, commit `e866fe33`), not an oversight.
