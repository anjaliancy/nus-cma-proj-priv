# Understanding End to End — updated 2026-08-10

For picking up in a new chat. Full detail lives in
[plan_of_action_anjali_2026-08-05.md](plan_of_action_anjali_2026-08-05.md) and
[foundations_qa_2026-08-06.md](foundations_qa_2026-08-06.md).

## Why this thread exists

After [client feedback](client_feedback_2026-08-04.md) on the first full-scope MCTS
output flagged several real issues, Anjali (new RA) realized she'd been relying on
Claude to make sense of the codebase instead of building her own understanding — hence
the "explain-back" plan: reason through concepts herself first, Claude corrects/confirms
after, rather than Claude just explaining.

## What's done

1. **Business problem** — understood and confirmed: maximize network profit (not just
   save cost) by adding/removing ports and adjusting vessel operations, subject to hard
   rules that can never be broken.
2. **MILP basics** — objective, decision variables, constraints; why some variables must
   be integer/binary (e.g. port in/out — no such thing as 50% of a port call).
3. **MCTS basics** — node = one network snapshot, branch = one structural move (add/
   remove a port, change vessel class); MCTS searches discrete/structural moves, calling
   `solve_approximated()` (MILP) at each node to score it.
4. **Division of labor, confirmed correct**: MCTS controls discrete/structural decision
   variables; MILP optimizes the continuous ones (speed, cargo flow) given that
   structure, and returns the profit score.
5. Took and passed a 10-question self-check MCQ on all of the above (first version of
   the quiz had a design flaw — 9/10 correct answers were "B" — fixed by shuffling
   options; her actual answers/reasoning were correct both times).
6. **Started but paused**: a deeper walkthrough of hard vs. soft constraints and what
   the client (CMA CGM) actually scoped for this project, grounded in
   [constraint_implementation_audit.md](constraint_implementation_audit.md). Covered too
   much at once — needs to restart in smaller chunks.

## 2026-08-10 session — what CMA CGM actually asked for

Working through this via [constraint_implementation_audit.md](constraint_implementation_audit.md)
(the real audit of company-requested rules vs. what's actually built), in three buckets:
**(1) objective/costs, (2) rotation-shape rules, (3) allowed MCTS moves.** One bucket per
message, Anjali restates before moving on.

### Bucket 1: Objective & base constraints — DONE, restated correctly

The core idea: some rules are **walls** (hard — physically/logically impossible to
cross), and some rules are **fines** (soft — allowed to happen, but costs the network
money/points in the model).

- **Costs to count**: chartering (renting ships), bunkering (fuel), port-call fees,
  transshipment costs. All four go into the profit calculation.
- **Meet customer demand — soft.** Missing it is allowed, just penalized (a fine).
- **Vessel capacity — hard.** A ship can't carry more than it physically holds; there's
  no "50% over capacity." A wall, not a fine.
- **Cargo transit time — soft.** Late delivery is penalized, not forbidden — there are
  too many real-world reasons a shipment could be late to make it a hard rule.
- **Port operations time** — a ship can't do more loading/unloading than its time
  parked at port allows.
- **Speed** — 10 knots minimum is **hard** (a ship isn't useful slower than that);
  16.5 knots is a **soft** ceiling (going faster is allowed but penalized for extra fuel
  burn).

Anjali's own restatement (correct): ship capacity is hard because there's no partial
version of "no more room on the ship" — it's a fixed physical limit. On-time delivery is
soft because a ship can be late for many different real reasons, so the model allows it
to happen but charges a penalty fee instead of banning it outright.

### Bucket 2: Rotation-shape rules — CORE CONCEPTS DONE, restated correctly

What makes a single service line (route) "valid":

- **No repeating sub-routes**: the exact same A→B hop can't appear twice in one loop.
- **Max 20 unique ports per line.**
- **A port can be visited at most 2 times** per line (open decision — code=2 vs.
  document=3, still unresolved).
- **Every line must include ≥1 transshipment (hub) port** — a place where cargo can be
  unloaded from one ship and loaded onto another to continue its journey. Ships stay on
  their own fixed loops; it's the *cargo* that changes ships, not the ship's route.
  Needed because no single loop can directly serve every origin-destination pair with
  demand — hubs relay cargo between routes, like a connecting flight.
- **Max 2000 nautical miles between consecutive stops** — no giant open-ocean jumps.
- **Minimum 3 hours berthing time** — not physically realistic to load/unload faster.
- **Penalty if schedule "buffer" (slack/waiting time) exceeds 30%** — too much idle time
  means an inefficient route.
- **Cargo can transship (switch ships) at most 3 times** on its journey. Anjali's
  reasoning (correct): each extra hop adds both port-call/transshipment cost and transit
  time, risking the late-delivery penalty from bucket 1 — unlimited hops would let a
  route "solve" on paper while cargo takes forever and costs a fortune to actually move.
- **Frozen lines** (VSA/partner routes): shape and speed locked, cargo can still flow
  through them.

The two rules restated in depth (hub requirement, 3-transshipment cap) were the
substantive ones; the rest (no-repeat segments, ≤20 ports, ≤2 visits, 2000-mile leg cap,
3h berth, 30% buffer) are more mechanical guardrails that stop the model from generating
physically nonsensical routes.

### Bucket 3: Allowed MCTS moves — DONE, restated correctly

MCTS's actual toolbox of structural moves today, from the "Actions (MCTS)" table:

- **Add a port call** (regular or transshipment/hub stop) — ✅ implemented.
- **Remove a port call** — ✅ implemented.
- **Shift a port call** (move a stop to a different position in the loop) / **swap two
  port calls** (trade positions of two stops) — ⚠️ not a single dedicated move; achieved
  indirectly by chaining **remove + add**. Dedicated `shift_port`/`swap_ports` functions
  exist in `serviceline.py` but aren't wired into MCTS's move list.
- **Change vessel rank (ship size/type) or round-trip duration (weeks)** — deferred to
  "Tier-2," not yet available to MCTS. **Correction made during discussion:** speed is
  *not* in this deferred group — speed is already MILP's job (bucket 1's 10–16.5 kt
  rule), so it was never MCTS's problem. Vessel rank and duration *are* discrete/
  structural like add/remove-port, so they conceptually fit MCTS's job description —
  the deferral is a scope/complexity decision (phasing the project, keeping the search
  space small at first), not a logical requirement that they belong elsewhere.

**Net takeaway**: today MCTS really only has **add-port** and **remove-port** as direct
moves; everything else is either reconstructed from those two (shift/swap) or
intentionally out of scope for now (vessel rank, duration).

## 2026-08-10 session (cont.) — data sources behind the MILP/MCTS

Walked through every raw data file CMA CGM provided (all in `data/input/` and
`data/data_2024-12-23/`, loaded by `data_reader.py`), grouped into 5 categories:

1. **The fleet** — `Vessel_Nominal.csv`: one row per ship type (rank), with capacity,
   daily rental cost, and a fuel-burn curve across speeds 10–18.5 kt (0.5 kt steps).
   Fleet size is treated as unlimited in the data.
2. **The ports** — `Port_Dataset.csv` (182 ports, basic facts) + `Port_Productivity.csv`
   / `Portcall_Costs.csv` / `Port_WaitingTimes.csv` / `Port_ManTimes.csv` (detailed
   operating numbers, 56 CNC ports only) + `PORT_CALL_Details_Dataset.xlsx` (fallback
   operating numbers for the other ~126 ports) + `port_APAC.csv` (the APAC-only subset —
   this is what currently *implicitly* enforces the "route can't leave APAC" behavior
   from the audit's open decision #2).
3. **Distances** — `SAILING_DISTANCE_Dataset.csv` + `Distances_CNC_Dataset.xlsx`:
   nautical miles between every port pair.
4. **Demand** — `Demand_Dataset.xlsx` (weekly TEUs per origin-destination pair, broken
   down by day of departure) + `demand_CNC_adjusted_comp.csv` (adds *expected transit
   time* per OD pair — what the bucket-1 "cargo transit time (soft)" penalty is measured
   against).
5. **Existing routes** — `proforma_CNC.csv` (CMA's real current routes, used as the
   optimizer's starting point) + `CURR_LINES_Dataset.xlsx`/`_detail` (the frozen/VSA
   lines from bucket 2 whose shape can't be changed).

**One-sentence summary**: everything downstream (MILP costs, MCTS moves) is built out of
combinations of these 5 raw categories — ships, ports, distances, demand, existing
routes.

**Open thread, not yet answered**: why does demand need a *day-of-week* breakdown and
not just a weekly total? (Asked, session ended before Anjali answered — pick up here.)

## 2026-08-10 session (cont. 2) — data table walkthrough, column by column

New plan: go through every data table's columns one by one (fleet, ports, distances,
demand, routes), then the output template and how to judge if an output is "correct."

### Table 1: `Vessel_Nominal.csv` (fleet) — DONE

One row = one vessel type/rank (not an individual ship).

- `vrank` — vessel type ID. `sizeclass` — human-readable TEU range label (e.g.
  "1500 - 1999"), descriptive only. `cap_nom` — the exact TEU number the MILP actually
  uses for the capacity hard-wall from bucket 1; `sizeclass` is just which bucket
  `cap_nom` falls into.
- `cost_charter` — daily rental cost. `cons_canal`/`cons_port`/`cons_man`/`cons_sea` —
  fuel consumption in specific operating modes (canal transit, at port, maneuvering,
  baseline).
- `cons_10.0kn` ... `cons_18.5kn` (18 columns, 0.5 kt steps) — a **fuel lookup table**.
  Real fuel-vs-speed is a curve (~cubic — 2x speed ≈ 8x fuel), which would make the MILP
  nonlinear and slow/unsolvable. Pre-computing 18 discrete values lets the solver treat
  speed as "pick one row from a table" — a simple linear choice. This is why speed in the
  model is restricted to 0.5 kt increments: it's a deliberate linearization trick, not an
  arbitrary real-world detail. Anjali's restatement (correct, after one correction of
  direction): removing the 0.5 kt grid would reintroduce the nonlinear curve and blow up
  solve time/complexity.

### Table 2: `Port_Dataset.csv` (182 ports, core facts) — MOSTLY DONE

One row = one port.

- `PortID`, `Longitude`/`Latitude` — identity/location.
- `MaxDraft` — max hull depth the port can accommodate. **Hard wall**: a vessel's draft
  must be ≤ port's `MaxDraft`, or the ship physically can't enter. This means the
  add-port MCTS move must check not just "insert port X" but "can *this line's assigned
  vessel type* legally call at X." Anjali's restatement (correct, tightened from "port
  can't handle larger ships" to specifically draft, not size/capacity — though the two
  correlate in practice).
- `TranshipmentCost`, `StorageCost`, `DaysFree` — not yet discussed in depth.
- `TranshipmentCapacity` — **investigated via code search, not just data-read**: despite
  the name implying a quantity, only 15/182 ports have a non-zero value, and all 15 are
  set to exactly `1` — all APAC hub ports (Ningbo, Shanghai, Shekou, Qingdao, Xiamen, HK,
  Yokohama, Gwangyang, Busan, Port Klang, Singapore, Keelung, Kaohsiung, Vung Tau). Not
  referenced anywhere in solver logic (`data_reader.py`, `servicegraph.py`) — only
  appears in a data-validation test (`tests/test_port_csv_validation.py`) that checks
  it's present/non-null, not what it means. Working conclusion: this is really a binary
  `is_hub` flag (matches bucket 2's transshipment-hub requirement) mis-stored/mis-named
  as a 0/1 "capacity" column, likely used upstream in building the hub list rather than
  read directly by the MILP. **Flagged as worth confirming with whoever owns the
  data/model** — misleading column name.
- `MaxDailyPortCall` — not yet discussed in depth.

### Table 3: Distances — DONE, grounded in a real discrepancy

Two files, different formats, and the code (`data_reader.py:358-402`) picks between
them: `Distances_CNC_Dataset.xlsx` (`Distance Matrix` sheet, wide matrix, ~58 ports,
**primary**) is tried first; `data_2024-12-23/SAILING_DISTANCE_Dataset.csv` (long format
`Port Departure`/`Port Arrival`/`Sailing Distance (Nautical miles)`, all 182 ports,
**fallback**) fills gaps CNC doesn't cover.

Anjali correctly predicted the risk unprompted: **if a pair exists in both files with
different values, CNC silently wins with no warning** — this is a real, not just
theoretical, risk. Verified with actual numbers: **CNDLC↔CNLYG** — legacy says 341.222
(→) / 343.256 (←, i.e. legacy encodes direction-dependent distance), CNC says 334.9 both
directions (CNC assumes symmetry). **CNSHA↔SGSIN** (Shanghai–Singapore, a major lane) is
entirely missing (`NaN`) from the CNC matrix — legacy fallback supplies 2350.7 nm, which
is why the fallback exists at all.

**Working style note**: after the abstract version of this table's explanation, Anjali
asked for concrete data (actual row values, not descriptions) — this is now the default
approach for every remaining table, not just when requested.

### Table 4: `Demand_Dataset.xlsx` (Sheet1) — IN PROGRESS, paused mid-explanation

Real columns (found via `pd.read_excel(..., sheet_name="Sheet1")` — the default/first
sheet is a messy pivot-table summary, NOT what the code reads): `POL_POD`, `LOAD_PORT`,
`DISCHARGE_PORT`, `DEPARTURE_DAY`, `Transit Days`, `TEUS`.

Code (`data_reader.py:412-445`, `read_demand_data`) builds **7 separate demand
matrices**, one per weekday (`Mon`...`Sun`), plus a summed `total_demands` matrix.
Verified real example: `VNSGN-AUSYD` appears twice, both `DEPARTURE_DAY = Sun` (88 TEUs
+ 30 TEUs) — code sums same-pair-same-day rows together; it does **not** distinguish
which "batch" gets which ship.

**Day-of-week question (the original open thread from earlier in this doc) — now
answered**: liner shipping runs **fixed weekly schedules** — a service line calls at each
port on ~the same day every week. If cargo is ready Sunday but the assigned ship's
rotation doesn't reach that port until Tuesday, the cargo waits — eating into `DaysFree`
before `StorageCost` (table 2) kicks in, and adding to transit time (bucket 1's soft
late-delivery penalty). A single weekly total would hide this timing entirely. **Anjali's
first answer** ("might be a different ship carrying the 88 vs the 30") was a reasonable
guess but not the mechanism — corrected, not yet restated back by her (session paused
here for a break).

Anjali's restatement of the day-of-week mechanism (2nd attempt, correct): cargo must be
ready on/before the ship's fixed weekly visit day; this is what lets the model calculate
wait time and storage fees.

### Table 5: `demand_CNC_adjusted_comp.csv` — DONE

Columns: `POL_POD` (combined string, code does `pol, pod = pol_pod.split('-')`), `TD_Exp`
(expected transit days), `TH_Exp` (expected transit hours — combined in code as
`td_exp + th_exp/24.0`, just a data-formatting convention from the source export, not
conceptually meaningful on its own), `TEUS`. No `DEPARTURE_DAY` column.

Code (`read_demand_with_transit_time`, `data_reader.py:447-498`) computes a **demand-
weighted average** transit time when the same `POL_POD` appears in multiple rows (real
example: `BDCGP-CNSHA` rows of 21.0d×70TEU and 21.5d×5TEU → weighted avg ≈21.03 days).

**Why two separate demand files** (verified with real counts, not guessed): 200 unique
ports / 35,494 rows in `Demand_Dataset.xlsx` vs. **56** unique ports / 956 rows in
`demand_CNC_adjusted_comp.csv`. The 56-port figure matches the same "core CNC ports"
subset already seen in `Port_Productivity.csv`/`Portcall_Costs.csv`/etc. So this isn't
two independent datasets — `demand_CNC_adjusted_comp.csv` is the full demand file
filtered down to this project's actual in-scope ports, with transit-time expectations
added (needed for the bucket-1 late-delivery soft-penalty benchmark, only relevant within
that scope). Anjali's restatement (correct on 2nd pass, after first pass needed
tightening from "why are they separate" to "because it's the 56-port project subset").

## Open / next steps

**Current focus**: go table by table through every data source's columns, using real
row-level data (not abstract descriptions — established preference), then the output
template and how to judge output correctness.

Order: fleet ✅ → ports (in progress, 3 cols left: `TranshipmentCost`, `StorageCost`,
`DaysFree`, `MaxDailyPortCall`) → distances ✅ → demand ✅ → **existing routes (next:
`proforma_CNC.csv` + `CURR_LINES_Dataset.xlsx`/`_detail`)** → output template.

1. Demand day-of-week breakdown question — deferred, not abandoned; fold into the demand
   table walkthrough when we get there.
2. **Two unresolved decisions from the audit doc** (not yet discussed with Anjali):
   per-port visit cap (code=2 vs. document=3), and whether "route can't leave APAC"
   should be an explicit constraint.
3. **After the foundation is solid**: return to tracing the actual client-feedback
   issues, starting with BBX2/BBX3 capacity (issue 1) as the first explain-back exercise
   on real code — [client_feedback_2026-08-04.md](client_feedback_2026-08-04.md).

## Working style reminder for next session

- **One concept per message, wait for her to respond before adding the next.** Stacking
  multiple new ideas (e.g. hard/soft constraints + client scope + open decisions all at
  once) overwhelmed her — explicitly flagged as unwanted.
- Let her reason/restate first; correct after, don't lead with the answer.
- Quiz-style checks are welcome but must have shuffled answer positions.
