# Project Concept — Plain-Language Overview

A plain-English guide to what this project does, what we've done recently, and how to
check it. No code or jargon. (For code explanations see `EASY_UNDERSTAND.md`.)

---

## 1. What this project is actually about

CMA CGM is a large shipping company. They run **container ships on fixed loops** — like a
bus route, but for cargo. A ship sails Port A → Port B → Port C → back to A, over and over.
Each such loop is called a **service line** (or just "line").

The goal of this project: **use a computer to design the best loops** — which ports to
visit, how many ships to use, and how fast to sail — so that all customers' cargo is
delivered **as cheaply as possible**.

There are two pieces of software doing this:

- **The "optimizer"** (the part that uses the Gurobi solver): you give it a set of routes,
  and it calculates the cheapest way to run them — how many ships, what speed, and which
  cargo travels on which ship.
- **The "search" (MCTS)**: it tries *changing* the routes to see whether a different set of
  loops would be even cheaper.

Right now we are mostly working with the **optimizer** piece.

---

## 2. A few terms you'll hear (in plain words)

- **Service line / line** — one repeating ship loop (a route).
- **Proforma** — CMA's *current, real* set of routes (the starting point).
- **VSA (Vessel Sharing Agreement)** — a route run by a *partner* company. CMA can't change
  these, so we leave them fixed and only count their capacity.
- **TEU** — the unit for counting containers (one standard 20-foot container = 1 TEU).
- **Optimizer "status"**:
  - **optimal** = it found the best answer (good).
  - **infeasible** = it proved no answer can satisfy all the rules (means the rules
    conflict — usually a bug, not a crash).
- **MILP / Gurobi** — the math engine that does the optimizing. Gurobi is the solver; we
  have an academic license for it.
- **MCTS** — the search method that experiments with changing the routes.

---

## 3. What we've been doing recently

1. **Tidied up the project.** The files were disorganized, so we reorganized them into clean
   folders (`src/` for code, `data/` for data, `notebooks/`, `docs/`, etc.).
2. **Got it actually running.** Set up the Gurobi license so the optimizer runs on this
   machine.
3. **Applied two business rules** the company asked for:
   - Ships must sail between **10 and 18 knots** (their realistic speed range). Where the raw
     data had impossible speeds, we correct them (push up to 10 knots and add the saved time
     to waiting).
   - **Partner (VSA) routes are left untouched** — we don't redesign them, we just account
     for the cargo space they provide.
4. **Found and fixed a bug.** When the optimizer was run cleanly it kept reporting *"no
   possible solution"* (infeasible). The cause was a wrong number in how the code calculates
   **ship capacity** (a too-small internal limit that made a constraint impossible to
   satisfy for any multi-ship route). This is now corrected.

---

## 4. Are we on the right track? **Yes.**

After the fix, on a small test the optimizer:

- **Finishes successfully** — reports `optimal` (found the best answer it could).
- **Delivers 100% of the cargo** — all 21,260 containers in the test get routed.
- Produces a **sensible cost** (see section 5 for what the cost is made of).

Before the fix it was completely stuck (infeasible). Now it runs start-to-finish. That is
real, concrete progress.

---

## 5. Understanding the cost number (important)

The headline cost (~$57 million in the small test) is **two different things added
together**:

1. **Real money to run the ships ≈ $8 million** — fuel, chartering the ships, port fees.
   This is the genuine operating cost.
2. **A "late-delivery penalty" ≈ $50 million** — this is **not real money**. It's a made-up
   penalty the model adds whenever cargo arrives late, to push it toward faster routes.
   (The business calls this "depreciation of cargo value if it arrives late.")

> Think of pizza delivery: the petrol to drive it is the real cost; the "refund if it's
> late" is a penalty we put on ourselves to stay on time. The total looks big, but most of
> it is the late-penalty, not actual spending.

**Why is the late-penalty so big right now?** Because we are testing on a **tiny slice — only
8 routes**. With so few routes, a lot of cargo has no fast path and arrives late, so the
penalty is large. On the **full network (31 routes)** there would be far less lateness, so
that penalty should shrink a lot.

**Comparison with before:**
- **Old number (~$10.9 billion):** the model couldn't carry much of the cargo at all, and
  "couldn't carry it" carried a giant penalty.
- **Now (~$57 million):** it carries **all** the cargo — just some arrives late, which is a
  much smaller penalty.

---

## 6. Talking points for an update call

- "The optimizer is now running end-to-end and producing valid, **optimal** solutions."
- "We fixed a bug that made it report **'no solution'** — it was a capacity-calculation
  error, now corrected."
- "On the test case it delivers **100% of demand** at a realistic cost."
- "We also **reorganized the codebase**, and the **speed (10–18 knots)** and
  **partner-route (VSA)** business rules are in place."
- "Next step: run it on the **full network** (31 routes instead of the 8-route test), then
  move on to the route-search (MCTS) and tuning."

**Honest caveat to mention:** we're currently on a tiny 8-route test, so the headline cost
is inflated by the late-delivery penalty; on the full network that should drop.

---

## 7. What's next

- Run the optimizer on the **full 31-route network** (not just the 8-route smoke test).
- Then work on the **route search (MCTS)** and **hyperparameter tuning**.
- Possibly review how strong the late-delivery penalty should be (a tuning question, separate
  from the bug fix).

---

## 8. How to check it yourself (so you're not just taking our word for it)

In `notebooks/test_mcts_kickstart.ipynb`:

1. **Kernel → Restart Kernel**, then run the cells down to the baseline solve.
2. Look for **`Solver status: optimal (GUROBI)`** — that means it worked.
3. Check that **TEU fulfilled = TEU input** (all cargo delivered).
4. The **root cost** is the model's total objective (real ship cost + the late-delivery
   penalty described in section 5).

> Note: editing a code file does **not** update an already-running notebook — you must
> **Restart Kernel** for changes to take effect.
