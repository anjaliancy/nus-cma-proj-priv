# Constraint Implementation Audit

Audit of the constraints/actions in *remaining tasks in CMA project* against the actual
code (MILP in `servicegraph.py`, line rules in `serviceline.py`, actions in `rl_utils.py`,
data handling in `data_reader.py`). Checked 2026-07-05.

**Summary:** almost everything is implemented, including many items the source document
still lists as "uncompleted". The **Singapore ≥72.5% transshipment-share** rule was added
2026-07-12 (soft by default, hard mode available). Two items need a decision: the
**per-port visit cap (code=2 vs document=3)** and whether **"route in/out of APAC"**
should be explicit.

---

## Objective & base constraints (MILP) — implemented

| Item | Status | Location |
|---|---|---|
| Chartering / Bunkering / Port-call / Transshipment cost | ✅ | `servicegraph.py:1057` (chartering) + bunker/portcall/transship exprs |
| Satisfy all demand (soft) | ✅ | `eps` slack + penalty, `servicegraph.py:1526` |
| Vessel capacities | ✅ | line-capacity constraint, `servicegraph.py:1539` (big-M fixed 2026-06-29) |
| Respect cargo transit time (soft) | ✅ | tardiness penalty, `servicegraph.py:1482` |
| Max ops ≤ port stay / productivity | ✅ | `servicegraph.py:1102` |
| Speed 10 kts (hard) – 16.5 kts (soft), penalize above | ✅ | floor at KTS-min + soft cap, `servicegraph.py:1160` |

## Line rotation constraints — implemented in `serviceline.py::check_valid` (L289)

| Item | Status | Location / note |
|---|---|---|
| No repeating sub-routes (directed edges) | ✅ | Case 3, `serviceline.py:310` |
| Unique ports in a service ≤ 20 | ✅ | Case 5, `serviceline.py:328` |
| Ports called more than once ≤ 2 | ✅ (doc: "uncompleted") | Case 6, `serviceline.py:335` |
| Every line visits ≥ 1 TS port | ✅ (doc: "uncompleted") | Case 7, `serviceline.py:343` |
| Max direct port-to-port leg ≤ 2000 mi | ✅ (doc: "uncompleted") | Case 8, `serviceline.py:350` |
| Minimum 3 h berthing time | ✅ (doc: "uncompleted") | `servicegraph.py:1105` (`min_berthing_days`) |
| Line penalized if buffer > 30% | ✅ (doc: "uncompleted") | `servicegraph.py:1261` (`buffer_violation_ub`) |
| POL–POD pairs connected by ≤ 3 transshipments | ✅ (doc: "uncompleted") | path enumeration capped at 3, `servicegraph.py:523` |
| Frozen lines: rotation & speed fixed, flow modifiable | ✅ | frozen lines excluded from actions `servicegraph.py:414`; flow still routes |

## Flow constraints — mostly implemented

| Item | Status | Location / note |
|---|---|---|
| Cargo transshipped only at select ports | ✅ (doc: "uncompleted") | `ALLOWED_TRANSSHIP_PORT_IDS`, `data_reader.py:18`; used via `filtered_by_transship_capacity` |
| ≥ 1 day between ETB2 and ETD1 for a transshipment | ✅ (doc: "uncompleted") | modeled in transit time, `servicegraph.py:1470` |
| **Singapore transshipments ≥ 72.5% of SG/MY/ID transshipments** | ✅ | `servicegraph.py::fulfill_demands`, gated by `turnon-singapore_transship_share` (off by default); soft slack penalty or hard constraint via `ctrparam-singapore_transship_mode` |

## Actions (MCTS)

| Action | Status | Note |
|---|---|---|
| Add a (regular/transshipment) port call | ✅ | `'add'` in `rl_utils.py:22`, explained `servicegraph.py:273` |
| Remove a port call | ✅ | `'delete'` in `rl_utils.py:22` |
| Shift / slide a port call; swap two port calls | ⚠️ not primitive MCTS actions | achievable via combined add+delete (as the source doc notes); dedicated `shift_port`/`swap_ports` exist on `ServiceLine` but are not wired into the action generator |
| Change vessel rank / speed / round-trip duration | — deferred | source doc marks these as **Tier-2 scheduling** |

---

## Open items / decisions

1. **⚠️ Per-port visit cap: code = 2, document = 3.** Default `max_line_visit = 2`
   (`port.py:56`), enforced at `serviceline.py:324`. One-line change if 3 is intended.
2. **⚠️ "Route cannot come in and out of APAC"** — only *implicitly* satisfied: the loader
   keeps APAC-only ports (`data_reader.py:211`), so no route can leave APAC. No explicit
   constraint exists; decide whether an explicit rule is required.

### Notes
- Items the source document lists under "uncompleted" that are in fact **done**: ports
  called >once ≤ 2, ≥1 TS port per line, 2000-mile leg cap, 3 h berthing, buffer>30%
  penalty, ≤3-transshipment routing, select-port transshipment, and the 1-day ETB/ETD gap.
- Several rules (buffer>30%, transit/tardiness, 1-day transship gap) are modeled as **soft
  penalties**, not hard constraints — consistent with the document's "(soft)" labels.
