# Session Summary — 2026-09-16 to 2026-09-21

Continuation of the client-feedback and MCTS work. Branch: `reorg-structure-final` (note: not
`reorg-structure` — the earlier August session docs use the old branch name). Full commit history
is the source of truth for exact code changes; this doc is for picking the thread back up in a
fresh chat.

## Fixed and pushed this session, in commit order

1. **`2beef05`** — Added `scripts/scoped-run/run_scoped_baseline.py` and `run_scoped_mcts.py`.
   Solve a *scoped* subset of the network (originally: all VSA + all FIX + the 5 OWN lines named
   in the original client feedback) instead of the full 31-line network, because the full network
   was assumed to take 2+ hrs to even build. **This assumption turned out to be largely wrong —
   see the efficiency finding below.**
2. **`d825a11`** — Fixed the same `cargo_flow_routes`-gets-silently-dropped bug (found in the new
   scoped scripts) in the older `scripts/export_mcts_best_network.py` too:
   `pd.ExcelWriter(..., engine='openpyxl')` in default mode replaces the *whole* workbook, so any
   sheet not explicitly re-written in that call gets deleted.
3. **`5766eef`** — Committed the scoped-run scripts' example outputs as reference templates.
4. **`d19a494`** — **Major finding.** Profiled why the full network was assumed to take 2+ hrs.
   Turned up something bigger than expected: `data_reader.py`'s `read_sailing_distance_data()` was
   looping over the sailing-distance CSV row-by-row (`for _, row in df.iterrows()`, 877k+ rows),
   which alone took ~44s — *more* than the cvxpy objective-construction issue it was expected to be.
   Vectorized it into a bulk `.map()` + one NumPy assignment; verified byte-identical output vs.
   the old loop (0 differing cells); ~37.6x faster. See
   [mcts_efficiency_investigation_2026-09-16.md](mcts_efficiency_investigation_2026-09-16.md).
5. **`24cff31`** — Added MCTS tree persistence for the prof's feedback ("remember what MCTS already
   tried, commit to a decision, don't redo useless work"). `MonteCarloTree.commit_one_step()` finds
   the best node so far, takes the first action toward it, and re-roots the tree there, discarding
   losing siblings. `committed_action_trace()` keeps a human-readable record across
   save/reload. Wired into `run_scoped_mcts.py` (`--fresh` to start over, `--tree-file` to choose
   where the tree is saved). **Known open bug, documented in the commit message: resuming a saved
   tree and finding no improvement crashes on the final re-solve** — the resumed graph's `Port`
   objects were created in a previous process and are compared by identity (`Port` has no
   `__eq__`) against the current run's freshly-built `PortGraph`, so every `has_port()` check
   fails and the network looks fully disconnected. Not yet fixed. Doesn't affect `--fresh` runs.
6. **`f9fb610`** — **The big one.** Found and fixed why MCTS kept finding tiny/repetitive
   improvements. `expand()` scored never-tried actions with `random.gauss(shared_mean, c_param)`
   and compared that guess directly against already-explored children's real values — since every
   untried candidate shared the same base mean, which one "won" depended only on independent
   per-candidate noise, **never on `c_param`'s magnitude** (proved empirically: a 3.5-million-x
   change in `c_param` produced byte-identical search behaviour on a fixed seed). In practice this
   meant the search converged onto whichever action got lucky early and almost never tried
   anything else — every run before this fix landed on the same single line, YCXCNC, regardless of
   network scope or hyperparameters (an abandoned tuning notebook from months ago,
   `notebooks/tune_mcts_hyperparams.ipynb` / a stray duplicate at `src/tune_mcts_hyperparams.ipynb`,
   hit this exact symptom independently and was abandoned after one flat result).

   Fix: standard UCT practice — try every untried action for real at least once before ever
   comparing options by guesswork. First version of the fix picked exactly one untried action and
   gave up for the epoch on failure; since only ~39% of "feasible" actions at the root actually
   pass the stricter validation inside `add_child()`, an unlucky streak stalled the search
   entirely — fixed to keep retrying different untried actions within the same call until one
   succeeds.

   **Result, verified on the real full network:** before the fix, best full-network result was
   $157,968 (0.41%), always on YCXCNC alone. After the fix, same config (mipgap=0.02, 20 epochs):
   **$7,808,130 (18.07%)**, across two different lines (BBX2CNC committed, CS2CNC queued next). See
   [scoped_mcts_run_result_2026-09-21.md](scoped_mcts_run_result_2026-09-21.md).
7. **`c6fe9fd`** — Documented the above result and wrote a reusable
   [client-feedback regression-check procedure](client_feedback_regression_check_2026-09-21.md)
   (all 8 original items reconfirmed not regressed — 5 via tests/direct evidence, 2 via manual
   output inspection since they have no dedicated test, #4 still N/A/not implemented).

All pushed to `origin/reorg-structure-final`, currently at `c6fe9fd`.

## Other findings worth knowing

- **The "2+ hour full network" problem is largely solved.** The full 31-line network now builds
  and solves a baseline in ~130s (actual Gurobi solve: ~10s; rest is cvxpy problem construction,
  now dominated by the objective-loop pattern documented in the efficiency doc, not data loading).
  There may be little reason to keep using the scoped-down subset going forward — the scoped
  network's baseline cost (~$1.76B) was ~95% a *fake* unfulfilled-demand penalty from artificially
  excluding 10 real OWN lines, not real economics. The true full-network baseline is ~$39-47M
  (varies with solver mipgap — see below).
- **Loose `mipgap` (the old default 0.10) was hiding real MCTS results in solver noise.** Two
  nominally-identical full-network baseline solves varied by ~17% just from mipgap/seed
  differences — bigger than the real improvements MCTS was trying to detect. Tightened to 0.02 in
  the successful run; this is now the value to use going forward, not the script's old default.
- **Answered the client's three original column questions directly** (from
  [client_feedback_2026-08-04.md](client_feedback_2026-08-04.md)): what `vrank_mix` means, why
  `capacity` shows decimals (nominal capacity × a fractional `capacity_scale`, minus a flat
  `capacity_reserve`), and the difference between `capacity` (fleet total) and
  `weekly_capacity_teu` (that total ÷ the rotation's cycle weeks).
- Git identity wasn't configured on this machine at the start of this session — now set globally
  (`user.name=anjaliancy`, `user.email=anjaliancy.a@gmail.com`), shouldn't need to be redone.

## Still open / not done this session

- **The resume-crash Port bug** (`24cff31`'s known bug, above) — not fixed. Needs re-attaching a
  resumed tree's lines' ports to the current run's `PortGraph` by port ID after loading.
- **VSA stay-time soft-lock (client feedback #4)** — still not implemented, pre-dates this session.
- **Duplicate notebook file**: `notebooks/tune_mcts_hyperparams.ipynb` and
  `src/tune_mcts_hyperparams.ipynb` are the same notebook (the `src/` copy has one extra cell);
  `src/` is very likely a stray duplicate from a past "re-add working-tree files" commit and
  should probably be deleted, but this wasn't done — flagged for Anjali to confirm first.
- **Untracked leftover files not committed** (mostly superseded by the post-fix result):
  `data/output/scoped_baseline_20260916_080017.xlsx`, three `data/output/scoped_mcts_20260917_*.xlsx`
  files (all pre-exploration-fix), and `data/output/scoped_mcts_tree.pkl` (a stale tree from before
  the fix). Candidates for cleanup, not yet removed.
- **The successful 18.07% run only explored 11 tree nodes out of 7,441+ candidate actions at the
  root alone.** There is very likely more improvement available — either by resuming
  `data/output/scoped_mcts_tree.pkl` (once the resume-crash bug is fixed, or if the run happens to
  find and commit an improvement every time so the buggy re-solve path is never hit) or by running
  a longer fresh search. Not yet attempted.
- The `select()`/`pucb()` code path still uses a similar noisy-guess pattern for children that have
  been *born* but not yet had their first real rollout (a smaller, lower-priority version of the
  bug just fixed in `expand()` — flagged during the fix but deliberately not touched, since it's a
  much lower-impact case: it only affects how quickly an already-committed-to child gets its first
  real solve, not whether new nodes get tried at all).
