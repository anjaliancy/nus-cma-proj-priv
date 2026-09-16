# MILP build-time efficiency gap — 2026-09-16

Follow-up to the known issue in [progress_summary_2026-09-11.md](progress_summary_2026-09-11.md):
the full 31-line/182-port network takes 2+ hours to solve end-to-end, stuck in **cvxpy problem
construction** rather than the Gurobi solve itself. That doc flagged the issue but didn't
investigate it. This doc records a first look at *why* it's slow and what a fix would involve.
**Nothing has been changed yet** — this is findings only, no code touched.

## Plain-language summary

Adding a cost piece to the total isn't a real number addition yet — it depends on decisions
the solver hasn't made (vessel count, speed, etc.), so cvxpy has to write a "remember to add
this later" note each time. Doing that one piece at a time, in a loop, means one note gets
wrapped inside the next, thousands of times over on the full network. Handing cvxpy the whole
batch of pieces at once (`cp.sum(...)`) means it writes exactly one note for the entire batch
instead. Same final formula, same final cost — just far less repeated bookkeeping. That
bookkeeping, not the actual solving, is what's eating the 2+ hours.

## The clue

Every scoped-network run (`scripts/scoped-run/run_scoped_mcts.py`, 21 of the 31 lines) prints
this warning from cvxpy itself, even on the smaller subset:

```
UserWarning: Objective contains too many subexpressions. Consider vectorizing your CVXPY code
to speed up compilation.
```

cvxpy is telling us directly what the bottleneck is. This isn't the solver being slow on a hard
problem — it's the *Python code that builds the problem* doing more work than it needs to before
Gurobi ever starts.

## Root cause

[`servicegraph.py`](../src/cma/servicegraph.py)'s `solve_approximated()` (the main MILP builder,
~2700 lines) builds the objective by adding many small pieces one at a time inside nested Python
`for` loops — once per line, and for several terms, once per port within each line. For example:

- `obj_expr += line_stay_penalty_expr` inside a per-line loop
  ([servicegraph.py:1423](../src/cma/servicegraph.py#L1423))
- `obj_expr += line_buffer_penalty_ub_expr` / `..._lb_expr`, also per-line
  ([servicegraph.py:1491](../src/cma/servicegraph.py#L1491),
  [:1496](../src/cma/servicegraph.py#L1496))

Each `+=` creates a new cvxpy `AddExpression` node. cvxpy has to canonicalize (translate into
solver-ready form) every node in that tree individually. Doing that one scalar piece at a time,
across dozens of lines × up to ~10 ports each, produces a deep, lopsided expression tree that's
far more expensive to canonicalize than the same total sum built as one bulk array operation.

The file already does this correctly in a few places, showing the fix is known and available in
this codebase already — e.g. `7 * cp.sum(ship_vars @ daily_charter_costs)` at
[servicegraph.py:2292](../src/cma/servicegraph.py#L2292) builds an entire term as one vectorized
expression instead of a loop.

**Why this scales so badly on the full network:** it isn't that 182 ports is "too much data" for
the solver — cvxpy's canonicalization cost grows worse than linearly with the *number of
Python-level accumulation steps*, not with the size of the underlying arrays. Going from the
21-line scoped subset to the full 31-line/182-port network multiplies the number of these tiny
per-line/per-port additions, which is consistent with the jump from a normal ~20s build to 2+
hours.

## Why this isn't a quick fix

`solve_approximated()` produces the exact cost numbers the client has already scrutinized
line-by-line (see [client_feedback_2026-08-04.md](client_feedback_2026-08-04.md) and the error
attribution doc in `session_exports_2026-08-11/`). Rewriting a loop into a vectorized form is easy
to get subtly wrong — e.g. an off-by-one in which ports/weeks get included, or a sign error in a
penalty term — and the file has dozens of these loops across chartering, transshipment,
bunkering, portcall, transit-penalty, and buffer-penalty costs (roughly lines 1155–1727 for the
objective terms alone). Any rewrite needs to reproduce **byte-identical costs** on a known run
before it can be trusted on the real network.

## Profiling results (scoped network, 21 lines)

Ran `cProfile` on `scripts/scoped-run/run_scoped_baseline.py`, then re-measured with plain
`time.time()` checkpoints (no profiler overhead) to confirm the numbers, since cProfile itself
adds real per-call overhead — and disproportionately so for code that makes many small calls,
which is exactly what both suspects here do.

**Plain wall-clock breakdown, one scoped baseline solve:**

| phase | time |
|---|---|
| `read_sailing_distance_data` | 44.0s |
| `solve_approximated` (objective build + cvxpy canonicalize + Gurobi solve) | 25.2s |
| everything else (other data reads, `PortGraph` construction) | <1s |
| **Total** | **69.6s** |

Two takeaways:

1. **The bigger surprise:** `read_sailing_distance_data` — not `servicegraph.py` — is the single
   largest chunk on the scoped network. [data_reader.py:375](../src/cma/data_reader.py#L375) did
   `for _, row in df.iterrows(): ...` over the legacy sailing-distance CSV (877,786 rows,
   confirmed via cProfile's `pandas.Series.__init__` call count) — the exact same
   "one tiny piece at a time" pattern as the cvxpy issue above, just in plain pandas.
2. **The `servicegraph.py` issue is real but smaller than assumed** on this scoped subset (25.2s,
   not hours) — cvxpy's own canonicalization passes (`qp_matrix_stuffing`, `coeff_extractor.affine`)
   accounted for most of that, matching the "too many subexpressions" theory, just not yet at a
   scale that dominates the total.
3. **Still unresolved:** we have *not* profiled the true full 31-line/182-port network (the one
   that actually takes 2+ hours) — only the 21-line scoped subset. `read_sailing_distance_data`'s
   cost is fixed regardless of how many lines are scoped in (same CSV, same 182-port pool), so it
   can't be the reason the full network specifically blows up to hours. The likely explanation is
   that `servicegraph.py`'s canonicalization cost grows worse-than-linearly with model size, but
   this is still an inference, not a measurement — profiling the full network directly is the
   next step to confirm it, and is expensive to do (2+ hrs) precisely because it's the slow case.

## Fix applied: `read_sailing_distance_data` (2026-09-16)

Vectorized [data_reader.py:375](../src/cma/data_reader.py#L375): replaced the `iterrows()` loop
with a bulk `.map()` of port names to indices, a boolean mask for unmatched ports, and one
NumPy fancy-index assignment (`dist_matrix[from_idx, to_idx] = dists`) instead of one assignment
per row. NumPy's plain-assignment indexing applies duplicate indices in array order, so a
duplicate `(from, to)` pair still resolves the same way as before (last row in the CSV wins).

**Verified safe:** ran the old and new implementations side by side on the real data and compared
the resulting distance matrices with `np.array_equal` (which handles the `inf` placeholders for
unmapped ports correctly) — **0 differing cells**. Existing tests
(`tests/test_cnc_distance_loader.py`, `tests/test_integration_data_loading.py`, 11 tests) still
pass.

**Speedup:** 21.5s → 0.57s for this function alone in the verification run (37.6x). Not yet
re-measured as part of a full scoped/full-network run.

## Recommended next step

Profile the *full* 31-line/182-port network directly (same phase-timer approach used above) to
confirm whether `servicegraph.py`'s objective-building loops are really what turns the
now-reduced build time into 2+ hours, before attempting any rewrite of the cost formulas
themselves. Not yet done — this is the one profiling run expensive enough (2+ hrs) that it's
worth deciding deliberately when to spend it.
