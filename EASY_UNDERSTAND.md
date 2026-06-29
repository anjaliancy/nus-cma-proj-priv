# Easy-Understand Guide

A plain-language companion to the code. **No jargon without explaining it.** If you
are new to this project and nobody handed anything over, start here.

This guide explains the code file by file, function by function, in everyday words.
The actual `.py` files stay clean; the explanations live here.

---

## 0. What is this project, in one paragraph?

CMA CGM is a **container shipping company** — they move cargo across the ocean in
big ships full of metal containers. Their ships run on fixed, repeating routes,
like **bus routes for the sea** (e.g. Singapore → Bangkok → Ho Chi Minh → back to
Singapore, over and over). Each route is called a **service line**. This software's
whole job is to **design the cheapest set of routes that still carries all the
cargo**. Everything in the codebase serves that one goal.

---

## 1. Vocabulary you'll see everywhere

| Word | Plain meaning |
|---|---|
| **Vessel** | A ship. In the code it usually means a ship **type** (like "a Toyota Corolla"), not one specific ship ("my car"). |
| **Vessel class / rank** | Ships come in sizes. "Rank" is just small-to-big ordering: rank 1 = smallest, higher number = bigger ship. |
| **TEU** | The unit for counting containers. 1 TEU = one standard 20-foot container. A ship's **capacity** is how many TEU it holds. |
| **Service line** | One repeating ship route (the "bus route"). |
| **Chartering** | **Renting** a ship. You pay a daily rate, like renting a truck per day. |
| **Bunkering** | Buying **fuel** ("bunker fuel" = ship fuel). Key fact: faster ships burn *much* more fuel. |
| **Draft** | How deep a ship sits in the water. Shallow ports can't take deep ships. |
| **Knots (kts)** | Speed at sea (nautical miles per hour). These ships go ~10–18 knots. |
| **Port call** | One stop at a port (loading/unloading containers). |
| **Transshipment** | Moving a container off one ship and onto another at a hub port to continue its journey. |
| **Demand / OD pair** | How many containers need to go from an Origin port to a Destination port ("OD" = Origin–Destination). |
| **VSA** | Vessel Sharing Agreement — a route run by a *partner* company where CMA just buys space (slots). CMA can't change these. |
| **Proforma** | The "as-is" real-world data: CMA's actual current routes and their details, used as a starting point and for comparison. |
| **MILP / solver** | The math engine (Gurobi) that crunches all the costs and picks the cheapest plan. You don't need to understand its internals to read most files — many files just *feed it numbers*. |
| **MCTS** | "Monte Carlo Tree Search" — the part that *tries out* different route designs to find good ones. Think trial-and-error, but smart. |
| **DataFrame** | A table (rows and columns) from the `pandas` library. Like a sheet in Excel, but in code. |

---

## 2. `vessel.py` — the fleet (ship types and their costs)

**What this file is for (one line):** it's a **data holder** that stores the facts
about each ship type (size, rental price, fuel use) and offers small "fetch me this number" helpers that the cost-calculating code asks for later. Nothing clever happens here — no optimization, just storing and returning numbers.

It has **two classes** (a "class" is just a blueprint for an object that bundles
data + functions):

### `Vessel` — the fact sheet for ONE ship type

Think of it as a spec card: "Rank 5 ship, holds 3000 containers, costs \$X/day to
rent, burns Y tons of fuel at 14 knots."

- **`__slots__`** (the list at the top): a fixed list of *which facts* a ship type is allowed to store (capacity, draft, rental cost, fuel curve, speed limits…). It's a small memory/typo-safety feature — you can ignore it for understanding the logic. The comments next to each name just say what type of value it holds.

- **`__init__(...)`**: this runs automatically when a ship type is created. It just
  **saves** each fact onto the object. Inputs:
  - `v_rank` — the size ranking (1 = smallest).
  - `v_class` — a container-capacity band, e.g. `(100, 499)`.
  - `capacity` — how many containers (TEU) it holds.
  - `draft` — how deep it sits in the water (metres).
  - `daily_chartering_cost` — daily rental price (USD).
  - `bunkering_cost_coefs` — the **fuel curve**: a list of `{speed, fuel-used}`
    pairs. Inside, it's turned into a small table (DataFrame) with a `speed` column  and a `consumption` (fuel used) column — one row per speed step (10.0, 10.5, … 18.5 knots).
  - `unit_bunkering_cost` — the **price of fuel** (USD per ton).
  - Two values are hard-coded here: `idle_bunkering_cost = 0.0` (fuel burned while parked is not modelled yet, so it's zero) and `min_speed = 10`, `max_speed = 18` (the slowest and fastest the ship may sail).

- **`__repr__()`**: just controls how the object prints — e.g. `"Rank 5 Vessel"`.
  (`__repr__` = the text shown when you print the object.)

### `VesselPool` — the WHOLE fleet (all the fact sheets together)

This is a list of all the `Vessel` fact sheets, plus how many of each CMA has, and the helper functions that hand numbers to the rest of the program.

- **`vessels_list`** — the list of ship types. **`numbers_list`** — how many of
  each type are available (same order).

- **`__init__(vessels_list, numbers_list)`**: saves those two lists.

- **`get_dataframe()`**: returns the fleet as a tidy two-column table (ship type + how many available). Handy for printing.

- **`get_bukering_costs()`** *(note: "bukering" is a typo in the code, but it's the real function name so we keep it)*: builds a **fuel-cost table** — for every ship type and every speed, "how many dollars of fuel per unit of time." It does this by taking each ship's fuel curve and multiplying the fuel used by the fuel price. Returns that table plus the starting (slowest) speed. Used when the program optimizes speed in detail.

- **`get_bukering_cost_middle()`**: a simpler version — just **one** fuel cost per ship type, measured at a medium speed. Used when the program doesn't want the full speed-by-speed detail.

- **`get_bunkering_cost_idle()`**: fuel cost while a ship is parked at port. Because `idle_bunkering_cost` is hard-coded to 0, this currently returns all zeros (parked-fuel cost isn't modelled yet).

- **`get_chartering_costs()`**: returns the list of **daily rental prices**, one per ship type.

- **`get_vessel_instance(v_rank)`**: "give me the fact sheet for the ship of this rank." (It finds it by position: rank 1 is first in the list, rank 2 second, etc.)

- **`get_number_of_types()`**: how many different ship types exist.

- **`get_speed_levels()`**: the list of speeds the fuel data covers (10.0 … 18.5).

**Mental model for the whole file:** `Vessel` = one ship type's spec card;
`VesselPool` = the binder holding all the spec cards + a few "look this up for me"
functions.

> ⚠️ Two quirks worth knowing (not bugs, just things to be aware of):
> 1. Several functions assume ship ranks are numbered `1, 2, 3, …` in the same order
>    as the list. If a rank were ever skipped, some lookups could line up wrong.
> 2. Parked-at-port fuel cost is always zero right now (not yet modelled).

---

## 3. `port.py` — the ports and the "map"

**What this file is for (one line):** it describes the **places** (ports) and the **relationships between them** (how far apart they are, how much cargo wants to ravel between them). Like `vessel.py`, much of it is data + lookups.

Three classes, building on each other:

### `Port` — the fact sheet for ONE port
"Singapore: here's its location, how much a stop costs for each ship size, how fast it loads containers, whether ships can switch here, how deep a ship it can take."
- **`get_producticity(vesselpool)`** *(yes, "producticity" is a typo in the code,but it's the real method name)*: how fast this port loads/unloads **each ship type** (containers per hour). Bigger ships usually get handled faster.
- **`get_portcall_costs(vesselpool)`**: the fee for one stop, per ship type. Ship types with no data get a big default number (so the optimizer avoids them).
- **`check_is_vessel_fit(rank)`**: can this ship type physically use this port?

### `PortPool` — ALL the ports together
A list of `Port` fact sheets plus convenient ways to find them:
- **`get_port(id)`** / **`get_port_by_idx(i)`** — find a port by its code or position.
- **`get_unique_index(port)`** — the position of a port in the list (used a lot,
  because the math works with numbered positions, not names).
- **`select([ids])`** — make a smaller pool from a chosen set of ports.
- **`filtered_by_transship_capacity()`** — just the ports that can act as **hubs** (where cargo can switch ships).
- **`plot(...)`** — draw the ports on a world map.

### `PortGraph` — the ports PLUS the connections between them
This is `PortPool` with extra tables attached:
- a **distance** table (nautical miles between every pair of ports),
- a **demand** table (how many containers want to go from A to B each week),
- an expected **transit time** table (how long cargo is expected to take).

This richer version is what the cost engine uses. Useful methods:
- **`get_distance(a, b)`**, **`get_demand(a, b)`**, **`get_transit_time_by_idx(...)`**.
- **`get_all_od_pairs()`** — every origin→destination that actually has demand
  ("OD pair" = Origin–Destination pair).
- **`get_demand_flows()`** — total containers coming in and going out of each port.
- The `filter_by_demand` option trims the map down to only the ports involved in
  real demand (keeps the problem smaller/faster).

**Mental model:** `Port` = one place; `PortPool` = the list of places; `PortGraph` =
the places **plus the distances and cargo demand between them** — i.e. the map with
traffic on it.

---

## 4. `serviceline.py` — ONE route (one ship line)

**What this file is for (one line):** it defines a single **service line** — one
repeating ship route (the "bus route") — and all the ways to read and edit it.

First, four small helper classes that describe pieces of a route:
- **`Segment`** — a single hop from one port to the next, e.g. Singapore → Bangkok.
- **`Slot`** — a Segment that belongs to a *specific* line (it knows which line uses that hop).
- **`Path`** — a sequence of slots that carries cargo from its origin to its
  destination, possibly **switching lines at a hub** along the way (transshipment).
- **`LineAction`** — an instruction to change a line (e.g. "add a port here").

### `ServiceLine` — the route itself
Holds: the route's name, the ordered list of ports it visits, which ship type it
uses (`vessel_rank`), how many weeks one full loop takes (`week`), the VSA-lock
fields (`frozen`, `frozen_speed`, `frozen_weeks`), its `service_type`
(`'OWN'` / `'VSA'` / `'FIX'`), and timing data from the proforma.

Its methods, grouped by what they're for:
- **Is this route legal?** `check_valid()` — enforces the rules (can't visit the
  same port twice in a row, at most ~20 ports, must include at least one hub, each
  hop ≤ 2000 nautical miles, etc.).
- **Basic facts:** `get_distance()` (total loop distance), `number_of_port()`,
  `tolist_port()`, `count_port_calls(port)`.
- **Editing the route** — each of these returns a **brand-new line** and leaves the
  original untouched: `insert_port`, `remove_port`, `move_port`, `swap_ports`,
  `shift_port`, `reverse_segment`, `rotate`. `apply_action(...)` runs a `LineAction`.
- **Finding paths:** `get_shortest_path(a, b)` — the way along this line from port a to port b.
- **Timing:** `set_buffer_profile(...)`, `get_buffer_wait_times()`,
  `set_schedule_profile(...)`, `get_schedule(...)` (works out the berth and
  departure time at each port).

**Mental model:** `ServiceLine` = the editable definition of one ship route. The
`Segment` / `Slot` / `Path` helpers are the little pieces used to describe routes
and how cargo moves along them.

> 💡 Why editing returns a *new* line instead of changing the old one: this lets
> the search (MCTS) try a tweak, score it, and throw it away without damaging the
> original — safe experimentation.

---

## 5. `servicegraph.py` — ALL routes together + the cost engine

**What this file is for (one line):** it represents the **whole network** (all the service lines at once) and contains the **cost engine** that scores a network: *"given these routes, what's the cheapest way to run them and carry all the cargo?"*

This is the most complex file in the project. Two main classes:

### `GraphAction` — an instruction to change the network
"For line #5, add port X between ports A and B." This is what the search proposes.

### `ServiceGraph` — the network + the engine
Holds the list of all service lines. Key methods:
- **`get_feasible_actions(...)`** — lists every valid change the search could make.
  It **skips frozen / VSA lines** (so partner routes are never modified). *(This is where the VSA "don't touch" rule takes effect.)*
- **`get_all_paths(...)`** — for every origin→destination with demand, works out the possible ways cargo can travel across the lines (allowing a few transshipments).
- **`solve_approximated(...)`** — the convenient entry point: it gathers the paths,  then calls `fulfill_demands`.  **`fulfill_demands(...)`** — **THE big one.** It builds a giant
  cost-minimization problem and hands it to the solver (Gurobi). It simultaneously
  decides:
  - how many ships of each type to put on each line,
  - how fast they sail,
  - how many weeks each round trip takes,
  - and how to route every container,

  so as to minimize **total cost** =
  *renting ships + fuel + port-stop fees + transshipment handling + penalties*
  (penalties for cargo it can't carry, cargo that arrives late, and schedules that
  are too tight or too loose). It returns the total cost, a cost breakdown, and
  KPIs (e.g. how much demand was actually carried).

**Mental model:** `ServiceGraph` = the full route map; `fulfill_demands` = the
calculator that scores how cheap that map is. The search calls this engine over and
over to compare different maps.

> ⚠️ The file also contains an older `fulfill_demands_2` and some profit functions.
> **Ignore those** — only `fulfill_demands` is the current, maintained engine.

---

## 6. `mcts.py` — the search that designs the routes

**What this file is for (one line):** it's the **smart trial-and-error** that tries many possible network changes and homes in on the cheapest ones. MCTS = "Monte Carlo Tree Search." It uses the cost engine (`fulfill_demands`) as its scorer.

Think of a huge menu of possible route tweaks — far too many to try all of them.
MCTS samples cleverly: it tries promising changes more, random ones occasionally,
and gradually focuses on the cheap region.

Two classes:

### `MonteCarloTreeSearchNode` — one candidate network in the search
Each node is one version of the network. It remembers how many times it's been
tried (`number_of_visits`), its running score (`sum_value`), and links to its
parent/children. Key methods:
- **`select(...)`** — walk down the tree to a promising node.
- **`expand(...)`** — create a new candidate by applying one change.
- **`rollout(...)`** — try some random further changes and **score** the result
  using the MILP cost engine.
- **`back_propagate(...)`** — push that score back up to the parent nodes.
- **`pucb / ucb`** — the formula that balances "use what we know is good" against
  "explore something new."
- **`current_state_reward()`** — the score = **1 ÷ cost** (cheaper network → higher
  score).

### `MonteCarloTree` — the whole search
You give it the starting network and the settings, call **`run(epochs)`**, then read
the best network found with **`get_best_node()`**. The settings (knobs) are:
- **`MCTS_EPOCHS`** — how many search iterations (more = better but slower).
- **`max_depth`** — how many changes deep it will explore.
- **`c_param`** — explore-vs-exploit balance.
- **`discount_fac`**, **`valid_weight_proportion`** — control how rollouts are
  scored/weighted.

**Mental model:** MCTS keeps asking the cost engine "is this tweaked map cheaper?",
remembers what worked, and reports the best map it found.

---

## 7. `data_reader.py` — loads all the data (the "loading screen")

**What this file is for (one line):** it reads the CSV/Excel data files and builds
the in-memory objects (fleet, ports, demand, distances, routes) that every other
file needs. **You run these functions first.**

Main functions:
- **`read_vessel_class_data()`** → a `VesselPool` (the fleet).
- **`read_port_data()`** → the ports.
- **`read_sailing_distance_data(portpool)`** → the distance table.
- **`read_demand_with_transit_time(portpool)`** → the demand + transit-time tables.
- **`read_cnc_proforma_data(portpool, vesselpool, dist_matrix)`** → CMA's real
  current routes as `ServiceLine` objects, plus metadata. *(The speed-fix and the
  VSA-freeze both happen in here.)*
- **`read_current_line_data(portpool)`** → the current/frozen lines (a different
  data source).
- **`normalize_leg_speed(...)`** → the helper that enforces the 10-knot speed floor
  (the speed fix).

**Mental model:** `data_reader` is the loading step — call its `read_*` functions to
turn the data files into the objects the rest of the program works with.

> ⚠️ The data file paths are **hard-coded constants near the top of the file** (they
> point at the current CMA dataset). To run on a different dataset you'd edit those
> constants (or add a new reader).

---

## 8. `output_summary.py` — turns the result into a readable report

**What this file is for (one line):** after the cost engine has solved, this file
takes that result and writes it out as a **human-readable table / Excel workbook**.
It does **not** solve anything or do any optimization — it's pure reporting.

It reads the dictionary that `fulfill_demands` returns (cost breakdown, per-line
diagnostics, KPIs) and reshapes it into spreadsheet rows.

Main functions:
- **`build_milp_output_summary_dataframe(...)`** — builds the main table: **one row
  per service line**, with columns like the ship type used, capacity, number of
  vessels, speed, sailing/operations/waiting times, cargo flow, fill factor (how
  full the ships are), and the cost breakdown. It adds a final **`__TOTAL__`** row
  that sums the numeric columns.
- **`build_run_metadata_dataframe(...)`** — a small key->value table of the run's
  headline numbers (total cost, each cost component, the KPIs, and solver status).
- **`export_milp_output_summary(...)`** — writes both tables into an Excel file (one
  sheet `summary`, one sheet `run_metadata`). It writes to a temporary file first
  then swaps it in, and gives a clear error if the Excel file is open/locked.

The functions starting with `_` (e.g. `_finite_float`, `_rank_mix`) are little
internal helpers for formatting numbers and text — you can ignore them.

**Mental model:** this is the "export to Excel" step. Run the engine, then hand its
result to these functions to get a clean report you can open in Excel or show your
prof.

---

## 9. `rl_utils.py` — valid-move finder (+ unfinished future code)

**What this file is for (one line):** its **one currently-important job** is to work
out, for a given network, which port add/remove moves are *valid* — that's what the
search uses to know its options. The rest of the file is **future, not-yet-used**
neural-network code.

### The part that matters now: `MatrixAnalyzer`
A network can be written as adjacency tables ("which port connects to which" for
each line). `MatrixAnalyzer.find_valid_k(...)` scans those tables and returns, for
each line, the legal **`add`** moves (insert a port between two connected ports) and
**`delete`** moves (remove a port and reconnect its neighbours), respecting limits
like how many times a port may be visited. `ServiceGraph.get_feasible_actions`
(section 5) calls this — so this is the engine behind "what changes can MCTS try?".

### The rest of the file: ignore for now
`GraphMatrixGenerator`, `GraphMatrices`, `DirectedGCN`, `Environment`, `MCTS`,
`train` — these are an **early sketch of a future "Layer 2"**: a neural network (a
Graph Neural Network) that would *learn* which moves tend to be good, to guide the
search. It is **not wired into the current pipeline**, it needs the `torch` library,
and parts of it have Chinese comments from the original author. Don't worry about it
while learning the live system — only `MatrixAnalyzer` is in use today.

**Mental model:** today this file = "list the legal moves." The neural-network
classes are a parked idea for later.

---

## 10. `utils.py` — small helpers (plotting + a week predictor)

**What this file is for (one line):** a grab-bag of small helper functions. Two
unrelated groups live here.

### Group 1: display helper
- **`display_two_figs(fig1, fig2)`** — shows two charts side by side in a notebook.
  Pure convenience for visualization.

### Group 2: the "week predictor"
A tiny **statistical model** (ordinary linear regression) that guesses how many
**weeks** a service line's round trip should take, based on features like its total
distance, number of stops, and surrounding demand. Functions:
- **`update_week_predictor(...)`** — fits/updates the regression from existing lines.
- **`apply_prediction(...)`** — uses the fitted model to predict weeks for new lines.
- **`create_week_predictor()`** — convenience: loads data and builds a predictor.
- (`_extract_line` / `_extract_lines` are internal helpers that turn a line into the
  numeric features the model needs.)

> NOTE: This week-predictor is mainly used by the **older** `fulfill_demands_2` path
> (the deprecated one mentioned in section 5). The current engine, `fulfill_demands`,
> lets the optimizer choose weeks itself, so you can treat this group as background.

**Mental model:** `utils.py` = odds-and-ends. The only thing to remember is the
week-predictor exists, but the current cost engine doesn't depend on it.

---

*That's every file in `src/cma/`. If any section still feels unclear, ask and I'll
expand it with a worked example.*
