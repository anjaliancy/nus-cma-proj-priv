# Mathematical Formulation: MCTS + MILP for Liner Shipping Network Design

This document compiles the mathematical model that drives the optimisation engine.
The engine has **two coupled layers**:

1. **Outer layer — Monte Carlo Tree Search (MCTS)** explores the discrete space of
   *network topologies* (which ports each service line calls, in what order). Each
   candidate topology is a *state*; each port insertion/deletion is an *action*.
2. **Inner layer — Mixed-Integer Linear Program (MILP)** evaluates a fixed topology
   by optimally assigning vessels, speeds, schedules and cargo flows, returning the
   minimum weekly operating cost. This cost is the *reward signal* that MCTS uses.

Notation convention: bold/upper-case symbols are decision variables, lower-case
symbols are data/parameters. Code references point to `src/cma/mcts.py` and
`src/cma/servicegraph.py` (method `fulfill_demands`).

---

## Part I — Monte Carlo Tree Search (outer layer)

### I.1 State, action, reward

- **State** $s$: a service graph $G$ (set of service lines with their port rotations).
- **Action** $a$: a `GraphAction` $(\ell, \text{cmd}, \text{loc})$ that adds or deletes
  a port in line $\ell$. The set of legal actions in state $s$ is $\mathcal{A}(s)$.
- **Transition**: $s' = T(s,a)$ deterministically applies the action.
- **Reward** of a state (cost-minimisation mode):

$$
r(s) \;=\; \frac{1}{C^\star(s)},
$$

where $C^\star(s)$ is the optimal MILP cost (Part II) of the topology in state $s$.
Using the reciprocal turns cost minimisation into reward maximisation, so a cheaper
network yields a higher reward. (In profit mode $r(s)=\text{profit}^\star(s)$.)
*Code: `current_state_reward`, `mcts.py:437`.*

### I.2 Node statistics

Each tree node holds a visit count $N(s)$, an accumulated value $W(s)$, and a prior
probability $P(s)$ (currently uniform; reserved for a future policy network). The
mean action value is

$$
Q(s) \;=\; \frac{W(s)}{N(s)}.
$$

### I.3 Selection — perturbed PUCB

Children are selected by a **Predictor + Upper-Confidence-Bound (PUCB)** score.
For a non-root node $s$ with parent $\mathrm{pa}(s)$:

$$
\mathrm{PUCB}(s) \;=\; Q(s) \;+\; c_{\text{param}}\, P(s)\,
\frac{\sqrt{N(\mathrm{pa}(s))}}{1 + N(s)} .
$$

Two special cases mirror the implementation (`pucb`, `mcts.py:418`):

- **Unvisited node** ($N(s)=0$): the exploitation term $Q(s)$ is unknown, so it is
  optimistically sampled from a Gaussian centred on the nearest visited ancestor
  ("estimated senior") $\tilde s$:

$$
Q(s) \;\sim\; \mathcal{N}\!\big(\mu_{\tilde s},\, c_{\text{param}}\big),
\qquad \mu_{\tilde s} = \frac{W(\tilde s)}{N(\tilde s)} .
$$

- **Root node**: the exploration term is randomised to keep the root "alive":

$$
\mathrm{PUCB}(\text{root}) = Q + c_{\text{param}}\,P\cdot
\frac{\sqrt{N}}{1+N}\cdot u, \qquad u\sim \mathcal{U}(0,\,1.5).
$$

A classical UCB1 variant is also implemented (`ucb`, `mcts.py:409`) as an
alternative scoring rule:

$$
\mathrm{UCB}(s) = Q(s) + c_{\text{param}}\sqrt{\frac{2\ln N(\mathrm{pa}(s))}{N(s)}} .
$$

### I.4 Expansion

From the selected node, the action with the highest PUCB among *unborn* actions is
instantiated as a new child. Unborn actions receive the same optimistic surrogate
value as above:

$$
\mathrm{score}(a) = \underbrace{\mathcal{N}(\mu_{\tilde s}, c_{\text{param}})}_{\text{surrogate } Q}
\;+\; c_{\text{param}}\,P(a)\,\sqrt{N(s)} .
$$

*Code: `expand`, `mcts.py:311`.*

### I.5 Rollout (simulation) with geometric discounting

This is the distinctive part of the model. Define the **discount factor**
$\beta = \texttt{discount\_fac}\in(0,1)$ and the **total weight**

$$
W_{\text{tot}} \;=\; \frac{1}{1-\beta} \;=\; \sum_{i=0}^{\infty}\beta^{i}.
$$

Starting from the node being evaluated, random legal actions are applied,
generating a trajectory $s_0 \to s_1 \to \dots \to s_m$. The MILP is solved at
each visited state. The rollout **stops** after $m$ steps once the truncated
geometric mass exceeds a target fraction $\rho = \texttt{valid\_weight\_proportion}$:

$$
S_m \;=\; \sum_{i=0}^{m}\beta^{i} \;=\; \frac{1-\beta^{m+1}}{1-\beta}
\;\ge\; \rho\, W_{\text{tot}} .
$$

The trajectory value is the **normalised discounted return** of the rewards along
the path (walking from the leaf $s_m$ back to $s_0$):

$$
V \;=\; \frac{W_{\text{tot}}}{S_m}\;\sum_{i=0}^{m}\beta^{\,i}\, r\big(s_{m-i}\big) .
$$

The factor $W_{\text{tot}}/S_m$ renormalises the truncated sum so that a short
(early-terminated) rollout is comparable to a full-horizon one. This $V$ is added
to the node's accumulators: $W(s_0)\mathrel{+}= V$, $N(s_0)\mathrel{+}= 1$.
*Code: `rollout`, `mcts.py:224`.*

### I.6 Back-propagation

The value is propagated to every ancestor. For each parent the update blends its
own immediate reward with the discounted child mean value:

$$
W(\mathrm{pa}) \;\mathrel{+}=\; r(\mathrm{pa}) \;+\; \beta\,\frac{W(s)}{N(s)},
\qquad N(\mathrm{pa}) \;\mathrel{+}=\; 1 .
$$

*Code: `back_propagate`, `mcts.py:292`.*

### I.7 Search loop and final answer

One **search step** = `select` → (`rollout` if leaf unvisited, else `expand`).
The tree runs for a fixed number of epochs (iterations). The recommended network
is the descendant with the highest reward $r(s)=1/C^\star(s)$ (equivalently lowest
MILP cost) found anywhere in the tree:

$$
s^\star \;=\; \arg\max_{s\in\text{tree}} r(s)
\;=\; \arg\min_{s\in\text{tree}} C^\star(s).
$$

*Code: `best_sub_node`, `mcts.py:131`; `MonteCarloTree.run`, `mcts.py:495`.*

#### MCTS hyperparameters

| Symbol | Code key | Meaning |
|---|---|---|
| $\beta$ | `discount_fac` | geometric discount on future rewards |
| $\rho$ | `valid_weight_proportion` | rollout-horizon fraction of $W_{\text{tot}}$ |
| $c_{\text{param}}$ | `c_param` | exploration constant in PUCB/UCB |
| $D$ | `max_depth` | maximum tree depth (root = 0) |
| — | `MCTS_EPOCHS` | number of search iterations |

---

## Part II — MILP cargo-allocation / fleet-deployment model (inner layer)

Solved once per evaluated topology by `ServiceGraph.fulfill_demands`. Backend:
Gurobi via CVXPY (fallbacks: SCIP, GLPK_MI, ECOS_BB).

### II.1 Index sets

| Set | Description |
|---|---|
| $\ell \in \mathcal{L}$ | service lines |
| $r \in \mathcal{R}$ | vessel classes (ranks) |
| $p \in \mathcal{P}$ | ports |
| $(o,d)\in \mathcal{OD}$ | origin–destination demand pairs |
| $\pi \in \Pi_{od}$ | candidate paths for pair $(o,d)$ (≤ 3 transshipments) |
| $e \in \mathcal{E}_\ell$ | directed legs (segments/slots) of line $\ell$ |
| $k \in \mathcal{K}$ | discrete round-trip durations in weeks, `week_levels` |
| $\kappa \in \mathcal{S}$ | discrete speed levels (knots), when speed optimisation is on |

### II.2 Decision variables

| Variable | Domain | Meaning | Code |
|---|---|---|---|
| $X_{od,\pi}$ | $\ge 0$ | weekly cargo flow (TEU) on path $\pi$ of pair $(o,d)$ | `demand_vars` |
| $Y_{\ell,e}$ | $\ge 0$ | weekly flow on leg $e$ of line $\ell$ | `flow_vars` |
| $V_{\ell,r}$ | $\mathbb{Z}_{\ge 0}$ | number of class-$r$ vessels on line $\ell$ | `ship_vars` |
| $N_{\ell,k}$ | $\{0,1\}$ | 1 if line $\ell$ uses a $k$-week round trip | `week_vars` |
| $Z_{\ell,\kappa}$ | $\{0,1\}$ | 1 if line $\ell$ sails at speed level $\kappa$ (optional) | `line_KTS_vars` |
| $t_{\ell,p}$ | $\ge 0$ | port-stay days of line $\ell$ at port $p$ | `matrix_stay_days` |
| $\epsilon_{od}$ | $\ge 0$ | unfulfilled demand slack for pair $(o,d)$ | `eps_vars` |
| $s^{+}_\ell,\, s^{-}_\ell$ | $\ge 0$ | buffer-violation slacks (above 30% / below 15%) | `buffer_violation_ub/lb` |

### II.3 Derived (linear) expressions

**Transshipment volume** at port $p$ on line $\ell$ — the cargo loaded/unloaded by
that line at that port, a linear combination of path flows:

$$
\mathrm{Tr}_{\ell,p} \;=\; \sum_{\substack{(o,d),\pi \\ \pi \text{ uses } \ell \text{ at } p}} X_{od,\pi}.
$$

**Line capacity** (weekly, before dividing by weeks):

$$
\mathrm{Cap}_\ell \;=\; \sum_{r} V_{\ell,r}\, \mathrm{cap}_r,
\qquad \mathrm{cap}_r=\text{TEU capacity of class }r .
$$

**Round-trip weeks / vessel count** (one-hot selected): $n_\ell = \sum_k k\,N_{\ell,k}$.

**Sailing days** of line $\ell$:

$$
\mathrm{sail}_\ell \;=\; 7\sum_k k\,N_{\ell,k} \;-\; \sum_p t_{\ell,p}
\;=\; 7\,n_\ell - \sum_p t_{\ell,p} .
$$

### II.4 Objective

$$
\min \; Z \;=\; \underbrace{Z_{\text{char}}}_{\text{chartering}}
+ \underbrace{Z_{\text{trans}}}_{\text{transshipment}}
+ \underbrace{Z_{\text{bunk}}}_{\text{bunker/fuel}}
+ \underbrace{Z_{\text{call}}}_{\text{port calls}}
+ \underbrace{Z_{\text{tardy}}}_{\text{transit penalty}}
+ \underbrace{Z_{\text{unmet}}}_{\text{unmet demand}}
+ \underbrace{Z_{\text{buf}}}_{\text{buffer penalty}} .
$$

**(1) Chartering cost** — $\gamma_r$ = daily charter rate of class $r$:

$$
Z_{\text{char}} \;=\; 7\sum_{\ell}\sum_{r} V_{\ell,r}\,\gamma_r .
$$

**(2) Transshipment (port-handling) cost** — $\theta_p$ = handling cost/hour at port
$p$; port-stay days $t_{\ell,p}$ are constrained by productivity (II.5):

$$
Z_{\text{trans}} \;=\; 24\sum_{\ell}\sum_{p} \theta_p\, t_{\ell,p} .
$$

**(3) Bunker (fuel) cost.** In the simplified mode (default) speed is fixed and
$\beta^{\text{bunk}}_r$ is the per-vessel weekly bunker rate:

$$
Z_{\text{bunk}} \;=\; 7\sum_{\ell}\sum_{r} V_{\ell,r}\,\beta^{\text{bunk}}_r .
$$

In the **speed-optimisation mode** the rate depends on the chosen speed level
$\kappa$ via $b_{r,\kappa}$, requiring the bilinear product
$W^{\text{vs}}_{\ell,r,\kappa}=V_{\ell,r}Z_{\ell,\kappa}$ (linearised in II.7):

$$
Z_{\text{bunk}} \;=\; 7\sum_{\ell}\sum_{r,\kappa} b_{r,\kappa}\, W^{\text{vs}}_{\ell,r,\kappa}.
$$

A soft speed cap multiplies $b_{r,\kappa}$ by `speed_penalty_multiplier` for
$\kappa$ above `speed_soft_cap_kts` (16.5 kts default).

**(4) Port-call cost** — $c_{p,r}$ = call cost of class $r$ at port $p$; cost scales
inversely with weeks (a $k$-week service incurs each call once per $k$ weeks). With
per-line call cost $c_\ell=\sum_{p\in\ell}\sum_r V_{\ell,r}\,c_{p,r}$:

$$
Z_{\text{call}} \;=\; \sum_{\ell}\sum_{k} \frac{1}{k}\, W^{\text{pc}}_{\ell,k},
\qquad W^{\text{pc}}_{\ell,k} = c_\ell\, N_{\ell,k}\ \text{(linearised, II.7)}.
$$

**(5) Transit-time (tardiness) penalty** — $\tau_{od}$ = expected transit time,
$\hat\tau_\pi$ = estimated path transit time (sailing at ~14 kts + transshipment
waiting), $\lambda^{\text{tt}}$ = penalty per TEU·day:

$$
Z_{\text{tardy}} \;=\; \lambda^{\text{tt}}\sum_{(o,d)}\sum_{\pi\in\Pi_{od}}
\big(\hat\tau_\pi - \tau_{od}\big)^{+} X_{od,\pi}.
$$

**(6) Unfulfilled-demand penalty** — $\lambda^{\text{u}}$ large:

$$
Z_{\text{unmet}} \;=\; \lambda^{\text{u}}\sum_{(o,d)} \epsilon_{od}.
$$

**(7) Buffer-violation penalty** — $\lambda^{+},\lambda^{-}$ penalise schedule
buffers outside the $[15\%, 30\%]$ band:

$$
Z_{\text{buf}} \;=\; \sum_{\ell}\big(\lambda^{+} s^{+}_\ell + \lambda^{-} s^{-}_\ell\big).
$$

### II.5 Core constraints

**(C1) Demand fulfilment** (soft lower bound + optional hard cap):

$$
\sum_{\pi\in\Pi_{od}} X_{od,\pi} \;\ge\; D_{od} - \epsilon_{od},
\qquad \epsilon_{od}\le D_{od},
\qquad \Big(\sum_{\pi} X_{od,\pi} \le D_{od}\Big).
$$

**(C2) Flow coupling** — leg flow must carry the cargo routed over it:

$$
Y_{\ell,e} \;\ge\; \sum_{\substack{(o,d),\pi \\ \pi \text{ uses leg } e \text{ of } \ell}} X_{od,\pi}.
$$

**(C3) Line-capacity** — leg flow ≤ weekly capacity $\mathrm{Cap}_\ell/k$ for the
selected $k$. Linearised with auxiliary $A_{\ell,k}\approx \mathrm{Cap}_\ell/k$ active
only when $N_{\ell,k}=1$:

$$
Y_{\ell,e} \;\le\; \sum_k A_{\ell,k}\quad\forall e\in\mathcal{E}_\ell,
$$
$$
A_{\ell,k}\le \bar U_k N_{\ell,k},\quad
A_{\ell,k}\le \frac{\mathrm{Cap}_\ell}{k},\quad
A_{\ell,k}\ge \frac{\mathrm{Cap}_\ell}{k} - \bar U_k(1-N_{\ell,k}),
$$

where $\bar U_k$ is a tight per-week capacity upper bound derived by greedily
packing the largest vessel classes (`_derive_weekly_average_capacity_upper_bounds`).

**(C4) Week one-hot:** $\sum_k N_{\ell,k}=1$; non-integer week levels forced to 0.

**(C5) Vessel identity** — number of ships equals number of weekly round trips:

$$
\sum_{r} V_{\ell,r} \;=\; n_\ell \;=\; \sum_k k\,N_{\ell,k}.
$$

**(C6) Port-operations / berthing** — stay days must cover handling work plus a
3-hour minimum berth ($g_p$ = gross productivity TEU/h, $\nu_{\ell,p}$ = #calls):

$$
t_{\ell,p} \;\ge\; \frac{\mathrm{Tr}_{\ell,p}}{24\,g_p},
\qquad t_{\ell,p} \;\ge\; \nu_{\ell,p}\cdot \tfrac{3}{24},
\qquad t_{\ell,p}=0 \ \text{if } g_p=0 .
$$

**(C7) Speed feasibility** (consistency of speed × time ≈ distance), with
$\mathrm{dist}_\ell$ the line round-trip distance. In fixed-speed mode:

$$
24\,(\kappa_{\min}-0.5)\,\mathrm{sail}_\ell \;\le\; \mathrm{dist}_\ell
\;\le\; 24\,(\kappa_{\max}+0.5)\,\mathrm{sail}_\ell .
$$

In speed-optimisation mode, with $W^{\text{ss}}_{\ell,\kappa}=Z_{\ell,\kappa}\,\mathrm{sail}_\ell$:

$$
24\sum_\kappa (\kappa+\tfrac{\Delta}{2})\,W^{\text{ss}}_{\ell,\kappa} \ge \mathrm{dist}_\ell,
\qquad
24\sum_\kappa (\kappa-\tfrac{\Delta}{2})\,W^{\text{ss}}_{\ell,\kappa} \le \mathrm{dist}_\ell .
$$

**(C8) Schedule-buffer band.** The schedule buffer ratio compares slack time to a
reference 16.5-kt schedule. With total waiting $T^{\text{wait}}_\ell$ and average
inverse speed $\bar v^{-1}_\ell$ (= $1/v_\ell$ fixed, or $\sum_\kappa Z_{\ell,\kappa}/\kappa$):

$$
\mathrm{num}_\ell \;=\; T^{\text{wait}}_\ell + \mathrm{dist}_\ell\Big(\bar v^{-1}_\ell - \tfrac{1}{16.5}\Big),
\qquad
\mathrm{den}_\ell \;=\; 168\, n_\ell .
$$

The buffer ratio $\mathrm{num}_\ell/\mathrm{den}_\ell$ is kept within $[0.15,0.30]$
via soft slacks:

$$
\mathrm{num}_\ell \le 0.30\,\mathrm{den}_\ell + s^{+}_\ell,
\qquad
\mathrm{num}_\ell \ge 0.15\,\mathrm{den}_\ell - s^{-}_\ell .
$$

**(C9) Schedule adherence (tethering, optional).** For each call $k$ on the line,
the estimated berth time must not exceed the proforma berth time plus a buffer
$\delta$ (`schedule_buffer_hrs`):

$$
\text{eosp}_0 + \frac{\mathrm{cumdist}_k}{\mathrm{dist}_\ell}\,\mathrm{sail}_\ell
+ \!\!\sum_{j<k}\! t_{\ell,p_j}
\;\le\; \text{ETB}^{\text{proforma}}_k + \delta .
$$

### II.6 Optional Big-M side constraints

**Transship ship-class restriction** — if $\mathrm{Tr}_{\ell,p}$ exceeds threshold
$A$, force at least one vessel of a class no larger than the port's best
transshipment class $k_p=\arg\max_r g_{p,r}$:

$$
\mathrm{Tr}_{\ell,p} - A \le M z,
\qquad \sum_{r\le k_p} V_{\ell,r} \;\ge\; z, \qquad z\in\{0,1\}.
$$

### II.7 Standard product linearisations (Big-M)

Every bilinear term of a (bounded integer/continuous) variable $u$ and a binary
$\delta$ is replaced by $W=u\,\delta$ with the four McCormick/Big-M inequalities:

$$
W \le M\delta,\quad W \ge -M\delta,\quad
W \le u + M(1-\delta),\quad W \ge u - M(1-\delta).
$$

This is applied to: the vessel×speed product $W^{\text{vs}}=V_{\ell,r}Z_{\ell,\kappa}$,
the speed×sail-days product $W^{\text{ss}}=Z_{\ell,\kappa}\,\mathrm{sail}_\ell$, the
callcost×week product $W^{\text{pc}}=c_\ell N_{\ell,k}$, and the capacity×week
product $A_{\ell,k}=(\mathrm{Cap}_\ell/k)N_{\ell,k}$.

### II.8 Output

The optimal objective $Z^\star = C^\star(s)$ is returned (plus per-line
diagnostics and KPIs) and becomes the MCTS reward $r(s)=1/C^\star(s)$.

---

## Part III — How the two layers couple

$$
\boxed{\;
\min_{\substack{\text{topology } s \\ \text{(MCTS search)}}}
\;\; C^\star(s)
\quad\text{where}\quad
C^\star(s) = \min_{X,Y,V,N,Z,t,\epsilon,s^\pm}
\big\{\, Z \ \text{s.t. (C1)–(C9)} \,\big\}.
\;}
$$

MCTS performs the **combinatorial outer search** over network structures it cannot
enumerate exhaustively; the MILP performs the **exact inner optimisation** of
deployment and routing for each structure. The reciprocal-cost reward, geometric
rollout discounting, and perturbed PUCB are the three mechanisms that let the
outer search converge toward low-cost networks within a limited evaluation budget.
