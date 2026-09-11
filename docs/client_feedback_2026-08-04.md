# Client Feedback — Full-Scope MCTS Output Review

**Date:** 2026-08-04

**Context:** First time an MCTS output on the full network scope was shared with the client. Feedback below, followed by the investigation response.

## Client Feedback

### Vessel rank/capacity
- BBX2 was downgraded to VRank 2 (742 TEUs nominal). Proforma info shared with them clearly states that 735 TEUs of capacity is reserved for external slotters.
- BBX3 was downgraded to VRank 2 (742 TEUs nominal). But somehow they calculated that the effective capacity owned by CNC is 2316 TEUs, which is not just higher than nominal capacity, it's not consistent with the capacity calculations used for BBX2.

### Rotation duration looks incorrect
After adding JPYOK to BMX, adding up all "seatime", "opstime", "waittime" and "mantime" shows that BMX has a total duration of 618.38 hours, or 25.77 days. This is clearly not an integer multiple of 7; claiming "3 vessels, 21 days" looks incorrect.

### Wait Times and Manoeuvring Times are treated as a variable instead of a constant parameter
All waiting times and manoeuvring times for BMX were set to 0. Proforma clearly states that these times add up to 197 hours.

### VSA services are frozen, yet their service schedules (speeds, stay times, sailing times) are being modified

### Speed limits are not respected
BBX has a constant sailing speed of 19kts.

### Ports with no demand are added to services
- CNCWN added to CP2. Filling factor before and after CNCWN is the same, and ops time at CNCWN = 0, meaning no movements are made. What is the point of it?
- Same observation and conclusion for the port MYLBU added to YCX.

### Cargo flow routing is not reported
Need this in order to properly review the quality of the output — especially how many of the cargo flows.

### Need clarity on columns
- What is "vrank_mix"?
- What is the difference between "capacity" and "weekly_capacity_teu"?

## Response / Investigation Findings

Investigated the current state of the code (`src/cma/servicegraph.py`, `src/cma/data_reader.py`, `src/cma/output_summary.py`, `src/cma/serviceline.py`, `src/cma/vessel.py`) point by point.

**1. BBX2/BBX3 capacity inconsistency — real gap, not a random bug.**
Two capacity tables never talk to each other: `data/input/Vessel_Nominal.csv` gives one flat nominal-capacity number per vessel rank (e.g. rank 2 = 742 TEU), and that's the *only* number the solver uses for capacity math (`data_reader.py:153`, `servicegraph.py:1545`). Separately, `data/input/proforma_CNC.csv` has per-line `cap_nom`/`cap_eff` (the "capacity reserved for external slotters" concept) — `cap_eff` is read and stored (`data_reader.py:634`) but **never used** in the actual constraints. The model reports the same generic per-rank number for any two rank-2 (or rank-5) lines, ignoring each line's real proforma capacity split. BBX2 and BBX3 aren't computed inconsistently with each other — both go through the identical (incomplete) formula. Fixable: wire `cap_eff` into the constraints.

**2. Rotation duration not a multiple of 7 — should not be possible in the current model; likely a stale/mismatched run.**
Duration is constructed to always equal exactly `7 × number of vessels` (`servicegraph.py:1216`), a hard equality, not computed after the fact and rounded. Recommend verifying which run/output the 25.77-day figure came from.

**3. Wait/manoeuvring time = 0 — intentional, fixed input, not optimized.**
These come straight from the proforma CSV as fixed numbers (`data_reader.py:671`) and are never touched by the solver. If BMX shows 0, that reflects the source input file for that run, not solver override — worth checking the input data.

**4. VSA "frozen" — partially as described, but a real gap found.**
Topology, weeks, and vessel class are locked (`data_reader.py:724`, `servicegraph.py:948`). Speed is deliberately left free (hard speed-lock previously made the solve infeasible — documented in code comment). New finding: **stay times are also free** for VSA lines — nothing pins them to proforma values, so both stay time and effective sailing speed can drift for a supposedly-frozen partner service. Likely the real source of "VSA schedules being modified." Recommend fixing: pin stay times for VSA lines.

**5. BBX at constant 19kts — two separate findings, not one.**

Speed range hardcoded globally as 10–18.5kts for every vessel class (`vessel.py:50`), not class-specific (itself a simplification). A 0.5kt schedule-feasibility buffer (`servicegraph.py:1252`) allows implied speed up to 19.0kts as the hard technical ceiling. Separately, a soft-cap penalty mechanism (fuel cost ×2 above 16.5kt) **already exists and matches the documented rule** (`servicegraph.py:1188-1194`, `ctrparam-speed_soft_cap_kts=16.5`, `ctrparam-speed_penalty_multiplier=2.0`) — the model is not missing the soft rule, so a hard cap at 16.5kt would be the wrong fix and would contradict the spec ("steaming above 16.5kt possible, but heavily penalized").

**5a. Real bug: soft-cap penalty threshold is miscalibrated.**
`cap_index = int(np.ceil(speed_soft_cap - speed_level0))` (`servicegraph.py:1191`) computes the index of the first penalized speed level assuming each array index is 1 full knot apart. The fleet's actual speed grid steps in 0.5kt increments (10.0, 10.5, ... 18.5), and the formula never divides by that step size. Result: the ×2 fuel penalty starts at **13.5kt**, not the intended **17.0kt** (first level above the 16.5kt threshold) — the penalized zone is roughly twice as wide as the rule specifies, hitting legitimate mid-range speeds it was never meant to touch. Fix: `cap_index = int(np.ceil((speed_soft_cap - speed_level0) / speed_step))`.

**5b. Open: why BBX still rides the ceiling at 19.0kt despite the penalty existing.**
An over-wide penalty zone (5a) would be expected to push speeds *down*, not explain a line sitting at the very top of the allowed range. Not yet root-caused — leading hypothesis is that the schedule-adherence ("tethering") constraint (`servicegraph.py:~1220-1251`, ties ETB times to proforma) is forcing BBX's speed to meet a schedule, overriding the fuel-cost deterrent. Needs its own trace before concluding a fix.

**6. Empty-cargo ports (CNCWN, MYLBU) — no guard exists.**
MCTS only checks rotation validity (no repeated ports, transshipment requirement, etc.) when inserting a port (`serviceline.py:821`). No check for whether the port moves any cargo. Only deterrent is the per-port-call cost in the objective (`servicegraph.py:1400`) — an economic soft-deterrent, not a hard rule. Fixable: reject/undo a move if resulting ops time and filling-factor change are both zero.

**7. Cargo flow routing not reported — data exists, just not exported.**
Solver computes full per-flow, per-path routing internally (`solution['demand routes']`, `servicegraph.py:1864`), but the output/export code only writes aggregated per-segment numbers (`output_summary.py:185`). Straightforward to add — missing export, not missing computation.

**8. Column definitions:**
- `vrank` = the single dominant vessel rank on that line.
- `vrank_mix` = all ranks in use with counts, e.g. `"5:2;6:1"`, for mixed fleets.
- `capacity` and `weekly_capacity_teu` — currently **identical**, both just per-vessel nominal capacity ÷ weeks. Looks like leftover duplicate columns from a refactor. A separate, correctly distinct `line_capacity_total_teu` column already exists for the "total" concept.

**Summary:** Points 2 and 3 are likely misreadings of the output or stale/mismatched data rather than code bugs — worth verifying which run those numbers came from. Points 1, 4, 5, 6, 7, 8 are real gaps, mostly "computed but not wired up / not exported" rather than actively wrong logic — fixes are additive, not a redesign. Highest-value fixes identified: effective-capacity wiring (1), VSA stay-time lock (4), zero-cargo-port guard (6), and OD-flow export (7).
