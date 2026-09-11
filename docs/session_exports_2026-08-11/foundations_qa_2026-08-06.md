# Foundations Q&A — Anjali, 2026-08-06

Part of the [plan of action](plan_of_action_anjali_2026-08-05.md): building an independent
understanding of the business problem, MILP, and MCTS through explain-back, before
returning to the [client feedback](client_feedback_2026-08-04.md) issues.

## Q1 — The business problem

**My answer:** A shipping line is basically a shipping company that carries cargo in its
ships from port to port in a regular fashion. Going to ports is cost inducing, due to a
bunch of things like how much cargo it carries, how much that port stop costs, waiting
time, etc. Some ports are not so useful because they're expensive to stop at and don't
even have much cargo, but this process also fetches the shipping company money because
of the cargo. The problem we want to solve is find a combination of ports to drop or
modify by adjusting vessel speed, cargo qty etc. to save them money.

**Correction:** Not just *dropping* ports — also *adding* them if there's untapped
cargo. And the goal isn't "save money," it's **maximize profit** (revenue minus cost) —
sometimes spending more is correct if it earns even more back.

## Q2 — Constraints vs. optimizing

**My answer:** We need to maximize profit (not just save money — sometimes spend more
money knowing you'll make more money), but while pursuing this, some things just cannot
be modified come what may — vessel speed must be in a certain range, a ship cannot carry
more than what it can, the loop time should be exactly a weekly multiple.

**Correction:** None — this was correct as stated.

## Q3 — Decision variables and constraints (MILP intro)

**My answer:** Decision variable is like the X variable — these are the ones we can
change and can optimize the objective, and here I think it's adding a port, vessel
speed, etc. The constraints are like conditions that need to be met no matter what. It's
sort of like in a relationship — my non-negotiables are my constraints and decision
variables are like those traits that can change based on partner to partner.

**Correction:** None — correct, and a genuinely good analogy.

## Q4 — Why some decision variables must be whole numbers

**My answer:** We can't have a port be 50% included, so some things need to be whole
numbers no matter what.

**Correction:** None — correct. (Port in/out, vessel class chosen, vessel count — all
either/or or count decisions, not smooth continuous ones.)

## Q5 — Why MCTS is needed on top of MILP

**My answer:** MILP is the approach to achieving an objective through certain variables
that we change, subject to certain fixed conditions. Trying out various possible
combinations of the variables is computationally expensive for MILP to handle alone, so
we add an outer layer search algorithm called Monte Carlo Tree Search, which is a
randomness-based approach. (Was still confused on what each node and branch is at this
point.)

**Correction:** None on the core logic — correct.

## Q6 — What is a node / branch in MCTS

**My answer:** A branch is a decision taken to the decision variables, and the node is
the resulting network after that decision.

**Correction:** None — correct. (Refined further in Q8: it's specifically the
*discrete/structural* decision variables that MCTS's branches change.)

## Q7 — Where does MILP fit in the MCTS tree

**My answer:** MILP is the approach of calculating the network — it is the outcome of
each node, in the sense that it represents the objective at each node subject to the
changes of the decision variables and the meeting of the constraints.

**Correction:** MILP isn't computed once at the end — it's called at (essentially)
every node MCTS visits, via `solve_approximated()` in
[servicegraph.py](../src/cma/servicegraph.py). Given the structure locked in by the
branches taken so far, it optimizes the remaining continuous variables and returns a
profit/feasibility score for that node.

## Q8 — Division of labor between MCTS and MILP

**My answer (first pass):** MCTS does the looping of changing the decision variables,
and MILP is what gets you the objective's value at each node after these decision
variable adjustments.

**My answer (worked example):** Say 5 variables and 2 constraints exist. MCTS does a
simulation and changes variable 1 & 2 (e.g. it changes speed and adds a port), then this
is passed to MILP, which takes what value MCTS gave for 1 & 2, and for 3–5 checks the
optimal value, then calculates the final objective, which in our case is revenue.

**Correction:** Two fixes —
1. Speed is *not* something MCTS sets — it's continuous, so it belongs to MILP.
   MCTS sets discrete/structural things: "is port X in this rotation" (yes/no), "which
   vessel class runs this rotation."
2. The objective is **profit** (revenue minus cost), not revenue alone — otherwise the
   model would just add every port with any cargo at all, ignoring cost.

**My answer (final, correct):** MCTS is used for the whole-number and yes/no stuff to
change, and MILP optimizes the continuous variables.

## Summary mental model

Business problem (maximize network profit under hard rules) → **MILP** (given a fixed
structure, optimizes continuous variables — speed, cargo flow — and scores profit) →
**MCTS** (searches which discrete/structural moves — port add/remove, vessel class — are
worth trying, calling MILP at each node it visits to judge that move).

---

## Self-check MCQ

Try these without scrolling back up. Answers are at the bottom.

**1. What is the network redesign problem actually trying to do?**
A. Minimize total sailing time
B. Save money by always removing the least-used ports
C. Maximize profit (revenue minus cost), subject to hard constraints
D. Minimize the number of ports visited

**2. Which of these is a hard constraint (can never be violated), not something to optimize?**
A. Vessel sailing speed within its allowed range
B. Whether a particular port is included in a rotation
C. How much cargo flows on a given route
D. Total profit of the network

**3. Why must "is Port X included in Rotation Y" be an integer (0/1) variable rather than a continuous one?**
A. Integers solve faster than continuous variables in general
B. Gurobi only accepts integer inputs
C. A port is either called at or not — there's no such thing as 50% of a port call
D. It doesn't need to be an integer, it's a modeling convenience

**4. In the MCTS tree, what does a "node" represent?**
A. A single decision variable
B. The final optimal solution
C. A constraint that must be satisfied
D. One complete snapshot of the network at a given point in the search

**5. In the MCTS tree, what does a "branch" represent?**
A. A complete alternate network
B. A constraint violation
C. The profit value of a node
D. One move applied to get from one node to the next (e.g. remove a port)

**6. Why can't MILP alone solve the "which ports to add/remove across the whole network" question directly?**
A. MILP can't handle integer variables at all
B. MILP doesn't know how to calculate profit
C. Testing every possible combination of structural changes is computationally too expensive to brute-force
D. MILP can only be used for continuous variables, never anything discrete

**7. At each node MCTS visits, what does it call to evaluate that node, and what does that call do?**
A. Nothing — MCTS scores nodes using random numbers
B. A separate MCTS sub-search
C. A hardcoded lookup table of port profitability
D. `solve_approximated()`, a MILP-style solve that fixes the discrete choices made so far and optimizes the remaining continuous variables to compute profit/feasibility

**8. Which decision variables does MCTS control, and which does MILP control?**
A. MCTS controls continuous variables (speed, cargo flow); MILP controls discrete ones (port in/out)
B. They both control the same variables independently
C. MCTS controls everything; MILP is only used to double-check the final answer
D. MCTS controls discrete/structural variables (port in/out, vessel class); MILP controls continuous variables (speed, cargo flow) given that structure

**9. True or false: the objective the solver maximizes is total revenue.**
A. True
B. False — it's profit (revenue minus cost)

**10. Fill in the blank: "MCTS searches which ______ moves are worth trying, calling ______ at each node to optimize the remaining variables and score that move."**
A. continuous / MCTS
B. random / Gurobi
C. profit / revenue
D. discrete/structural / MILP

---

### Answer key
1-C, 2-A, 3-C, 4-D, 5-D, 6-C, 7-D, 8-D, 9-B, 10-D
