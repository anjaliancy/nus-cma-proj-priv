# VSA speed/schedule investigation — 2026-09-09

Follow-up to Meixi's feedback on the VSA schedule infeasibility issue (see
[client_feedback_response_2026-08-23.md](client_feedback_response_2026-08-23.md) for the
original ask). Started as "try Meixi's fix," ended up finding a much bigger, unrelated
issue in the solver. **Nothing in this doc is committed yet** — all code changes below
are uncommitted on `reorg-structure` (`data_reader.py`, `servicegraph.py`,
`serviceline.py`, `tests/test_service_type_constraints.py`).

## Background

Meixi's diagnosis: sailing time is computed two ways in this model - (a) fixed cycle
time minus port time, (b) distance ÷ speed - and she suspected these disagree because
published VSA speeds are nominal/rounded. Her proposed fix: keep speed locked (along
with rotation/timetable/port-stays/weeks, as already done), but stop treating
`speed × time = distance` as a hard MILP constraint - keep it only as a validation/
warning check.

## 1. Implemented Meixi's fix

- `data_reader.py`: VSA lines now get `frozen_speed` set (previously left `None`
  specifically to dodge the constraint below - see the old comment at
  `data_reader.py:759` for why).
- `servicegraph.py:1341-1351`: removed the hard equality
  `line_sailing_days × 24 × frozen_speed == line_distance`. Same relaxation applied in
  the discrete-speed branch (`servicegraph.py:1427-1443`).
- `servicegraph.py:1918-1938`: added a post-solve check per VSA line - computes
  `distance ÷ (24 × sailing_days)` and compares to the published speed, prints a
  warning above 5% mismatch, and stores the numbers in
  `line_diagnostics['schedule_speed_check']`.

**Result:** solves cleanly (4.6s on the 9 VSA lines, no infeasibility). But the
validation check immediately flagged that the "mismatch" isn't small:

| line | published (kt) | implied (kt) | mismatch |
|---|---|---|---|
| CS1CNC | 14.78 | 10.83 | 26.7% |
| JTXCNC | 15.34 | 11.60 | 24.4% |
| RMNCNC | 16.24 | 12.74 | 21.6% |
| CT8CNC | 14.84 | 12.15 | 18.1% |
| TIX2CNC | 14.47 | 12.00 | 17.1% |
| YSXCNC | 12.79 | 11.32 | 11.5% |
| CMS2CNC | 14.54 | 12.97 | 10.8% |
| CHN1CNC | 14.44 | 12.97 | 10.2% |
| CP8CNC | 12.03 | 11.82 | 1.8% |

Every single line's implied speed is *slower* than published, never faster - a
consistent direction, not scatter. That ruled out "random rounding noise" as the
explanation and sent us looking for a systematic cause.

## 2. Tried the second client suggestion (didn't help)

Second suggestion floated to us: recompute each leg's speed from distance/time and bank
any leftover time into waiting time (the same trick `normalize_leg_speed()` already
applies to anomalous sub-10kt legs in `data_reader.py`, generalized to every leg).

Tested it (reprocessed all 9 VSA lines' per-leg schedules this way, re-ran the solve).
**Mismatch barely moved** (e.g. CS1CNC: 26.7% → 26.6%). Conclusion: the per-leg proforma
data isn't the cause.

## 3. Traced it to `matrix_stay_days`

`line_sailing_days = 7 × vessel_weeks − port_stay_days`, and `port_stay_days` comes from
`matrix_stay_days`, a MILP decision variable (`servicegraph.py:1176`) that only has a
*floor* (must be ≥ real operations time) - nothing pulls it toward the real published
stay time. So the solver is free to shrink stay time toward that floor and let sailing
days (and therefore implied speed) drift.

**Built and tested a soft penalty** (`serviceline.py`: new `frozen_stay_days` profile +
`set_stay_days_profile()`/`get_stay_days_profile()`; `servicegraph.py:1347-1379`: penalty
term, off by default behind `turnon-vsa_stay_time_penalty`) - same style as the existing
buffer-violation penalty, not a hard lock (avoids the infeasibility risk a hard lock
already caused once for speed).

**Result: it worked exactly as designed** - with the penalty on, every VSA line's stay
time at *its own* rotation ports matched the real published schedule almost exactly
(e.g. CS1CNC: 11.00 real vs 11.00 MILP-picked). But the speed mismatch **still didn't
close**. That was the clue that broke the case open.

## 4. Found the real bug: phantom stay time at ports a line never calls

`line_port_stay_days` (used for the sailing-days math, `servicegraph.py:1307-1310`) sums
`matrix_stay_days` across **every port in the network**, not just the ports on that
line's own rotation. Checking line-by-line, several VSA lines carry large stay-time
values at a port none of them call: **CNQZH**.

| line | phantom stay at CNQZH (days) |
|---|---|
| CHN1CNC | 9.56 |
| CMS2CNC | 9.25 |
| CP8CNC | 5.54 |
| CS1CNC | 7.13 |
| YSXCNC | 6.34 |

None of these lines' rotations include CNQZH. Verified this wasn't a bug in our own
reporting/extraction code - pulled the raw solver variable directly (bypassing all
diagnostics code) and got the same numbers two independent ways.

**Ruled out as explanations:**
- Wrong port label / index mixup - checked the port-index round-trip for all 182 ports,
  zero mismatches.
- Wrong line index inside the solver - `ServiceGraph.__init__` just does
  `self.__lines_list = services`, no reordering (`servicegraph.py:343`).
- Cargo actually routing through CNQZH - enumerated every path the model could build
  with these 9 lines; none ever touch CNQZH for any of the affected lines. Confirmed
  directly: `transshipments[line, CNQZH]` is the literal Python int `0` for all 9 lines
  (temporarily instrumented and removed after confirming).
- MIP-gap solver slack - re-solved at MIPGap 1e-7 (Gurobi reported status "optimal" in
  8s, not a timeout); the phantom value barely changed.

**Confirmed it's a real, costly inefficiency, not a harmless artifact:** manually forced
`matrix_stay_days[:, CNQZH] == 0` for all lines (temporary constraint, removed after the
test) and total cost **dropped by $8.88M** (from $1,092,929,150 to $1,084,052,207).

That's the key finding: Gurobi reports the unmodified solve as mathematically
"optimal," yet a simple manual override finds $8.88M in savings it should have found on
its own. That points to a **numerical conditioning problem**, not a routing/data bug -
this model mixes very large constants (`BigM-portcall_cost`: 1e7–2e9,
`BigM-saildays`: 64–100) with small per-unit costs (CNQZH's rate is $22.22/day) in the
same MILP. That kind of scale mismatch is a known way for a solver's tolerances to
report "optimal" while leaving small-but-real inefficiencies unresolved.

## Why this matters beyond VSA

If the cause is numerical conditioning, it isn't specific to CNQZH, to VSA lines, or to
this investigation - it could be silently leaving cost on the table anywhere in the
model, on every run to date, with no error or warning to flag it. That's a bigger and
more fundamental issue than the VSA schedule mismatch we started out chasing.

## Status / next steps

- Meixi's fix (locked speed, hard constraint → warning): **working, not yet committed**.
- Stay-time penalty experiment: **working as designed, not recommended to merge as-is**
  - it doesn't fix the mismatch because the mismatch isn't really about stay time at a
    line's own ports; kept behind an off-by-default flag for reference.
- `line_port_stay_days` summing over the whole network instead of just a line's own
  rotation ports (`servicegraph.py:1307-1310`): confirmed real bug, not yet fixed.
- Numerical conditioning (Big-M vs small per-unit costs) causing "optimal" solves to
  leave real money on the table: confirmed real and reproducible on this one case, root
  cause and scope not yet investigated - proposed as the next thing to dig into.
