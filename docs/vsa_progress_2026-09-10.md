# VSA speed-mismatch fix — progress 2026-09-10

Continues [vsa_speed_stay_investigation_2026-09-09.md](vsa_speed_stay_investigation_2026-09-09.md).
Yesterday ended with two open threads: (1) the phantom-port / numerical-conditioning
bug, (2) closing out the VSA schedule infeasibility (Meixi) fix. Today closed the VSA
speed mismatch. **Nothing is committed** — all changes are uncommitted on
`reorg-structure` (`data_reader.py`, `servicegraph.py`, `serviceline.py`,
`tests/test_service_type_constraints.py`).

## TL;DR

The VSA "implied speed 10–27% below published" mismatch is fixed. It had **two**
independent causes, both needed fixing:

1. The sailing-days formula counted waiting + manoeuvring time as sailing time.
2. Once the hard `speed × time = distance` link was dropped (Meixi fix), nothing
   pinned VSA sailing days, so the solver set them arbitrarily.

After the fix, implied speed matches published within ~0.3% on 8 of 9 VSA lines; 7 of 9
also match exactly on the 0.5 kt vessel-speed grid. The 2 that don't are a rounding
boundary (RMNCNC) and one bad data cell in the proforma (YSXCNC) — parked, see below.

## 1. Phantom-port fix (from thread 1) — done, but not the speed-mismatch cause

`matrix_stay_days[line, port]` only had a lower bound, so for ports a line never calls
the solver could park stay time there. With `schedule_adherence` on, every VSA line
carried 5–12 phantom stay-days at **CNQZH** (a port none of them call).

Two edits in `servicegraph.py`:
- In the `matrix_stay_days` constraint loop: `matrix_stay_days[line, port] == 0`
  whenever `port_call_counts[line, port] == 0`. Permanent form of yesterday's
  `[:, CNQZH] == 0` probe.
- `line_port_stay_days` now sums only the line's own rotation ports, not all 182.

**Verified:** off-rotation stay-days are now exactly 0 on every VSA line.

**But:** removing the phantom stay did **not** move the speed mismatch (identical to the
pre-fix table). So yesterday's section-4 hypothesis — phantom stay dragging implied
speed down — does not hold. The phantom mass was a separate inefficiency. The
$8.88M figure from yesterday was on a different/fuller config and was not reproduced
here (9-line config moved by <$0.5M).

## 2. Real cause of the speed mismatch

A rotation cycle splits into **four** buckets, not two. For CS1CNC (4 weeks = 672 h):

| bucket | source column | hours | days |
|---|---|---|---|
| sailing | `timetonext` | 339 | 14.1 |
| stay | `staytime` | 264 | 11.0 |
| waiting | `time_wait` | 43 | 1.8 |
| manoeuvring | `time_manin` + `time_manout` | 26 | 1.1 |
| **sum** | | **672** | **28.0** |

The four buckets sum to the cycle time exactly for all 9 VSA lines (checked, diff = 0.0).

The model's formula was `sailing_days = 7 × weeks − stay`. It only subtracted **stay**,
so **waiting + manoeuvring fell into "sailing days"** — inflating sailing days and
deflating implied speed (`distance / (24 × sailing_days)`).

Cross-check: distance-matrix loop ÷ *true* proforma sailing hours reproduces the
published speed almost exactly (CHN1CNC 5430 / 376 h = 14.44 kt = published;
CS1CNC 4989 / 339 h = 14.72 vs 14.78). So the distance matrix is fine — earlier
"distance too short" reading was an artefact of the 2-bucket formula.

CHN1CNC was the tell: its MILP stay was *higher* than published yet it was still 10%
slow, because it has 144 h (6 days) of wait + manoeuvring being counted as sailing.

### Fix 2 — sailing-days formula

- `serviceline.py`: new `proforma_manoeuvre_times` list (per-port `manin + manout`, hrs)
  + `set_manoeuvre_times()` / `get_manoeuvre_times()` / `get_fixed_nonsail_hours()`
  (the last returns `sum(waiting) + sum(manoeuvring)` in hours, or 0.0 for lines with no
  proforma profile, e.g. MCTS-created lines — so their behaviour is unchanged).
- `data_reader.py`: populates `set_manoeuvre_times()` from the proforma alongside the
  existing buffer / schedule / stay-days profiles. Note proforma `manin`/`manout` differ
  from the port-level `Port_ManTimes.csv` values for every VSA leg — the proforma
  values are the ones that reconcile with the published schedule, so we use those.
- `servicegraph.py`:
  `line_sailing_days = 7 × weeks − line_port_stay_days − line_fixed_nonsail_days`
  where `line_fixed_nonsail_days = line.get_fixed_nonsail_hours() / 24`.

**On its own this changed nothing visible** — the solver just lowered the stay variable
by the same amount to keep sailing days where it wanted them. Needs Fix 3.

## 3. Nothing pins VSA sailing days → hard stay lower bound

With the Meixi fix, VSA speed is locked via the KTS binary but sailing days are no
longer tied to it. The objective is indifferent to VSA sailing days (VSA
chartering/bunker/portcall costs are excluded — partner-run), so the solver picks an
arbitrary value in a wide feasible window.

VSA stay time *is* part of the frozen partner timetable, so it should be held to the
published value. Two options considered:

- **Soft penalty** (the `turnon-vsa_stay_time_penalty` experiment code from yesterday):
  works, but needs the rate cranked to ~200,000/day before every line pins — at that
  point it is just emulating a hard constraint, less cleanly.
- **Hard lower bound** (chosen): `matrix_stay_days[line, port] >= published_stay` for
  VSA ports. A `>=` bound, not an `==` lock — it stacks with the operational stay floor
  and the higher wins, so it cannot cause the infeasibility a hard equality risked
  (CLAUDE.md item #4 concern). No rate to tune.

### Fix 3 — `servicegraph.py`

New block after the stay-penalty block: for each VSA line
(`line.frozen and line.frozen_rank_weeks` — FIX lines excluded, their rank/weeks/speed
stay optimisable), add `matrix_stay_days[line, port] >= published_stay_days` per port.
Gated by `turnon-vsa_stay_time_lock`, **default on**. The soft penalty flag is left in
place as the alternative.

## Results (9 VSA lines, schedule_adherence on; identical with it off)

| line | published kt | implied kt (after) | mismatch | 0.5-grid |
|---|---|---|---|---|
| CHN1CNC | 14.44 | 14.44 | 0.0% | 14.5 = 14.5 ✅ |
| CMS2CNC | 14.54 | 14.56 | 0.1% | 14.5 = 14.5 ✅ |
| CP8CNC  | 12.03 | 12.00 | 0.2% | 12.0 = 12.0 ✅ |
| CS1CNC  | 14.78 | 14.73 | 0.3% | 15.0 = 15.0 ✅ |
| CT8CNC  | 14.84 | 14.79 | 0.3% | 15.0 = 15.0 ✅ |
| JTXCNC  | 15.34 | 15.30 | 0.3% | 15.5 = 15.5 ✅ |
| RMNCNC  | 16.24 | 16.31 | 0.4% | 16.0 vs 16.5 ❌ (straddles 16.25; raw gap 0.07 kt) |
| TIX2CNC | 14.47 | 14.45 | 0.2% | 14.5 = 14.5 ✅ |
| YSXCNC  | 12.79 | 13.41 | 4.8% | 13.0 vs 13.5 ❌ (bad proforma cell — see below) |

- Solve time ~8 s, status optimal.
- Total cost ≈ $1,052.77M vs ≈ $1,052.30M pre-fix — up ~$0.5M, i.e. the solver gives up
  a small amount of *fictitious* saving it got from inflating VSA sailing days. Absolute
  numbers are from the reduced 9-line harness (dominated by an unfulfilled-demand
  penalty) — real value impact needs a full-network run.
- Service-type tests still pass.

## Parked: YSXCNC

YSXCNC route: SGSIN → MMRGN → MYPKG → MMRGN → SGSIN (MMRGN visited twice).
Every leg matches the distance matrix within ~2 nm **except** MMRGN → MYPKG:

| leg | distance matrix | proforma (vspeed × timetonext) |
|---|---|---|
| MMRGN → MYPKG (outbound) | 882 nm | 11.0 kt × 65 h = 715 nm |
| MYPKG → MMRGN (return)   | 882 nm | 13.5 kt × 65 h = 878 nm |

Same water, 715 vs 878 nm. The outbound leg's 11.0 kt is wrong (covering ~882 nm in
65 h needs ~13.6 kt). That one cell drags YSXCNC's published line-average speed to
12.79; the model's distance-matrix value gives 13.41, which is the more defensible
number. **This is a proforma data bug, not a model bug** — parked, revisit later.

## Open items

1. **Commit.** Nothing today is committed. Files: `data_reader.py`, `servicegraph.py`,
   `serviceline.py`, `tests/test_service_type_constraints.py`.
2. **Strip or keep the stay-time-penalty experiment** (`turnon-vsa_stay_time_penalty`,
   off by default) now that the hard lower bound supersedes it. Decision pending.
3. **Pre-existing bug in the Meixi-fix code**, `servicegraph.py:1549`: the lower-bound
   half of the `aux_W_speedsaildays` big-M linearisation is dedented out of its `for`
   loop, so it is only enforced for the top speed level. Inside `if not
   vsa_speed_locked`, so it does not affect the 9 frozen VSA lines, but is wrong for
   every non-frozen line. Belongs to the Meixi-fix thread.
4. **Numerical conditioning** (Big-M 1e7–2e9 vs $22/day costs causing "optimal" solves
   to leave money on the table): still open from yesterday, not investigated.
5. **Full-network verification**: the 31-line network is still the slow (~2 h) run; the
   fixes above are only verified on the 9-VSA-line harness.
6. **YSXCNC proforma cell** (item above).

## Files changed today

| file | change |
|---|---|
| `src/cma/serviceline.py` | `proforma_manoeuvre_times` + `set_manoeuvre_times` / `get_manoeuvre_times` / `get_fixed_nonsail_hours` |
| `src/cma/data_reader.py` | load per-port manoeuvring time from proforma |
| `src/cma/servicegraph.py` | phantom-port pin + rotation-only stay sum; sailing-days = `7·wk − stay − wait − manoeuvre`; VSA stay-time hard lower bound (`turnon-vsa_stay_time_lock`, default on) |
