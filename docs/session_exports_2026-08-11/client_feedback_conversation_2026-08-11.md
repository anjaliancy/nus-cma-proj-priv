# Client Feedback — Conversation Log (2026-08-11)

Record of the working session between Anjali and Claude tracing the client-flagged
issues in [client_feedback_2026-08-04.md](client_feedback_2026-08-04.md). Captures what
was asked, what was found, and what was decided — not just the final findings.

## Context going in

Session started continuing the data-table explain-back walkthrough (fleet, ports,
distances, demand — see
[understanding end to end 10-08-2026.md](understanding%20end%20to%20end%2010-08-2026.md)),
but Anjali was dealing with a migraine partway through and felt low about the day. She
asked to pivot to something more concrete and outcome-oriented: answering the client
feedback directly, and starting to fix real issues.

## 1. Picking the first fix — column definitions (item #8)

Given her state, Claude offered a menu of small, scoped feedback items rather than
tackling all 8 at once. Anjali picked **column definitions** (#8) as the lowest-risk
starting point.

**Finding:** `capacity` and `weekly_capacity_teu` in `output_summary.py` both read from
the same `weekly_capacity` variable — always identical, even though the solver
separately computes a real "total fleet capacity" number (`line_capacity_total_teu`)
that was simply never exported.

**Fix applied:** `capacity` now reads `line_capacity_total_teu` (total TEU across all
vessels on the line); `weekly_capacity_teu` stays as that total ÷ rotation weeks.
Verified with a manual mock-data run showing the two columns now differ correctly
(2000.0 vs 1000.0, matching the fixture already present in
`tests/test_output_summary_export.py`).

Anjali asked for the explanation of this fix multiple times, each time requesting it
**shorter** — ended on: *"The bug: both columns read the same variable. The fix:
`capacity` now shows total fleet TEU, `weekly_capacity_teu` stays as that ÷ weeks."*
**Working-style note:** she prefers short, plain explanations over
long/structured ones by default now, especially post-fix summaries.

Also explained `vrank_mix` (no bug — format `"rank:count;rank:count"`, e.g. `"5:2;6:1"`,
for mixed-fleet lines).

## 2. Item #6 (zero-cargo-port guard) — scoped, then deferred

Anjali next asked for #6 ("which is easiest"). Claude investigated and found it's
**not** a small fix: candidate "add port" moves are generated in
`get_feasible_actions()` (`servicegraph.py:404`) with zero cargo/demand awareness — the
only way to know if a port move actually carries cargo is *after* the MILP solves it,
inside `add_child()` in `mcts.py:181`. A correct fix means touching the core MCTS search
loop, not a one-line guard.

Claude flagged this complexity before proceeding and asked how to proceed (skip for
now / do it anyway / stop for the day). **Anjali chose to skip #6** and move to
verifying items #2 and #3 instead, which required no code changes.

## 3. Items #2 and #3 — one bug explains both

**Point #2** (client: BMX rotation duration = 25.77 days after adding JPYOK, "not an
integer multiple of 7"). **Point #3** (client: BMX wait/manoeuvring times all showing
as 0, when proforma says they total 197 hours).

Claude traced both and found they share **one root cause**, not two separate issues:

- `duration` in the output is a hard equality (`7 × selected_week`, `servicegraph.py:
  1216`) — mathematically cannot be a non-multiple of 7. The client's 25.77-day figure
  came from *manually summing* `seatime+opstime+waittime+mantime`, not from reading the
  `duration` column.
- `waittime`/`mantime` come from a static `port_details` list built once from the
  original `proforma_CNC.csv` row count for that line (`output_summary.py:174-183`).
  When MCTS adds a port (JPYOK, in this case), the line now has one more port than
  `port_details` was built for — the length check fails, and the code silently falls
  into a branch that **zeroes `mantime` entirely** and substitutes a different waittime
  estimate.

So: adding JPYOK broke the wait/man-time data (#3, a real bug — not stale/misread data
as first suspected), and the client's manual sum (which used the corrupted
wait/man-time figures) is why their total didn't land on a multiple of 7 (#2 — a
symptom of #3, not an independent bug).

## 4. Item #5 (speed limits) — proposed fix reconsidered

Anjali proposed changing the upper speed limit to 16.5kt, citing the spec: *"Vessel
speed must be between 10kts (hard) and 16.5kts (soft) — steaming above 16.5kts possible,
but heavily penalized."*

Claude checked the code before implementing and found a **soft-cap penalty mechanism
already exists** at exactly 16.5kt with a 2× fuel-cost multiplier
(`servicegraph.py:1188-1194`) — so hard-capping at 16.5kt would have been the wrong fix,
contradicting the client's own stated rule (soft, not hard).

Instead, found a real bug in how that existing penalty is calculated:

- **5a (confirmed bug):** `cap_index = int(np.ceil(speed_soft_cap - speed_level0))`
  (`servicegraph.py:1191`) doesn't divide by the fleet's 0.5kt speed-step, so the
  penalty zone starts at 13.5kt instead of the intended 17.0kt (roughly 2× too wide).
  Fix identified: divide by `speed_step`.
- **5b (still open):** an over-wide penalty zone would be expected to push speeds
  *down*, which doesn't explain BBX sitting at exactly 19.0kt (the hard ceiling: 18.5kt
  fuel-table max + a 0.5kt schedule-feasibility buffer). Leading hypothesis — the
  schedule-adherence ("tethering") constraint may be forcing BBX's speed regardless of
  fuel cost — not yet root-caused.

Both written up as separate line items in `client_feedback_2026-08-04.md` per Anjali's
request, rather than one combined explanation.

## 5. Item #1 (BBX2/BBX3 capacity) — explained, iterated for plain language

Anjali asked for the mechanism behind the capacity inconsistency. First explanation used
a table format and was too dense — she said she didn't understand it. Claude re-explained
as a plain narrative (ships have a nominal capacity; real usable capacity is smaller
because some slots are reserved for external "slotters"; the model ignores that reserved
figure and uses the same flat number for every line of a rank; BBX2 and BBX3 only
*looked* inconsistent because the client's manual math correctly used each line's real,
different numbers against a model that uses neither). Then asked for it shorter again —
settled on a 3-line bug/data/why-it-looked-inconsistent summary.

**Root cause confirmed in code:** `servicegraph.py:1545` builds line capacity from a
flat per-rank nominal number only (`Vessel_Nominal.csv`'s `cap_nom`); the real per-line
`cap_eff`/`cap_reserve` figures from `proforma_CNC.csv` are parsed into a metadata dict
(`data_reader.py:637`) but never read back out anywhere. **Anjali asked why** this
wasn't wired in — answer: two independent data-reading paths (one feeding the solver's
constraints, one feeding output metadata) were never connected; not a deliberate
decision.

## 6. Authorship / git-history audit

Anjali asked whether any of these issues were caused by her own past changes. Claude
answered by tracing `git blame`/`git log` directly (not from memory) for every issue
discussed, rather than guessing. Findings:

- **None of the 8 client-flagged issues trace back to Anjali's code.** Root causes come
  from Zhuang Linsheng (Feb–Aug 2025) and Darrell (a Dec 19, 2025 commit explicitly
  titled "...incomplete"), plus zxhalim15 (Feb–May 2026).
- **Anjali's own commit** (`e866fe33`, Jun 25, 2026) covers the VSA freeze logic —
  correctly recalled by her from memory as a deliberate fix for a real MILP
  infeasibility (locking a frozen VSA line's speed created a hard equality conflicting
  with the line's own schedule data). Verified against her own code comment — her
  recollection was accurate.
- The new gap found this session (VSA stay times not pinned) sits adjacent to her fix
  but wasn't in its scope — not a mistake in what she built, an omission next to it.

This authorship breakdown was compiled into
[client_feedback_error_attribution_2026-08-11.md](client_feedback_error_attribution_2026-08-11.md)
(table format, per Anjali's request for something pasteable).

## Open items / not yet done

- #6 (zero-cargo-port guard) — deferred, needs MCTS-loop-level change.
- #1 (BBX2/BBX3 capacity) — root cause identified, fix not yet implemented (wire
  `cap_eff`/`cap_reserve` into `servicegraph.py:1545`).
- #4 (VSA stay-time gap) — not yet fixed.
- #5b (why BBX rides the 19.0kt ceiling) — not yet root-caused.
- #7 (cargo flow routing not exported) — not yet implemented.
- #2/#3 — understood as one bug; the `port_details` length-mismatch fallback in
  `output_summary.py` not yet fixed.
- #8 — **done** (this session).

## Working-style notes for future sessions

- Prefers **short, plain explanations** — repeatedly asked to shorten even after
  simplifying once. Default to brief unless she asks for more detail.
- Wants findings **grounded in actual code/data**, not descriptions — this was already
  established earlier in the day for the data-table walkthrough and carried through to
  the bug investigations (real line numbers, real git commit hashes, real dates).
- Before making a "quick fix," check first whether it's actually small — #6 looked
  small from the client-feedback doc summary but wasn't; surfacing that complexity
  before diving in was the right call and she chose to defer rather than push through.
