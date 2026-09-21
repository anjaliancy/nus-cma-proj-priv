# Client feedback regression-check procedure — 2026-09-21

A repeatable checklist for confirming none of the 8 original client feedback items (see
[client_feedback_2026-08-04.md](client_feedback_2026-08-04.md) for the originals) have regressed,
after making changes to the code. Written up after doing this check by hand following the MCTS
exploration fix on 2026-09-21 - see
[scoped_mcts_run_result_2026-09-21.md](scoped_mcts_run_result_2026-09-21.md) for that check's
actual results.

## The three-step method

**1. Run the test suite** (from repo root, using the project venv):
```
.venv\Scripts\python.exe -m pytest tests/ -q
```
Takes a few minutes. Gives a clear pass/fail list. Anything with dedicated test coverage - if its
test still passes, that item didn't regress.

**2. When a test fails, don't assume it's a new bug.** Check when that test file was last changed:
```
git log -1 --format="%h %ad %s" --date=short -- tests/test_whatever.py
```
If the date is old and unrelated to what you just changed, the failure is very likely pre-existing
debt, not something you broke. Example: `test_output_summary_export.py` fails on an assertion that
the output workbook has exactly 2 sheets - but that assertion was last touched in May, months
before the `cargo_flow_routes` sheet (item #7) was even added in August. The test is stale, not the
code.

**3. For fixes with no dedicated test, check by hand.** Open a real output file the code just
produced and look at the actual numbers for something the fix should affect. A green test suite
only proves what's actually tested - for everything else, the real output file is the source of
truth.

## Item-by-item: what to check and how

| # | Item | Has a dedicated test? | How to check |
|---|---|---|---|
| 1 | BBX2/BBX3 capacity (`capacity_scale`/`capacity_reserve`) | Yes - `tests/test_demand_and_capacity_constraints.py` | Run the test |
| 2/3 | Wait/manoeuvring times after MCTS adds a port | No | Open a run's output `summary` sheet, find a line MCTS actually modified, check `waittime`/`mantime` at the new port's position are real non-zero numbers |
| 4 | VSA stay-time soft-lock | N/A - not implemented yet | Nothing to check - confirm it's still correctly *not* claimed as done anywhere |
| 5a | Speed soft-cap penalty calibration | Yes - `tests/test_speed_penalty.py` | Run the test |
| 5b | NaN `cap_scale`/`cap_reserve` crash guard | No | Run any full-network solve (some lines have NaN `cap_scale` in the source data) and confirm it doesn't crash with `"Element of a double array is Nan or Inf"` |
| 6 | Zero-cargo port-addition guard | No | Check `_is_zero_cargo_add`/`_reject_child_as_invalid` still exist in `src/cma/mcts.py`; look for tree node counts dipping during a real MCTS run (a rejected addition being pruned) as live evidence it's firing |
| 7 | Cargo flow routing export | Only a stale/wrong one (see above) | Open a run's output workbook, confirm the `cargo_flow_routes` sheet exists |
| 8 | `capacity`/`weekly_capacity_teu` duplicate columns | No | Open a run's output `summary` sheet, confirm `capacity` and `weekly_capacity_teu` show genuinely different values per row (they should differ by the line's `selected_week`, not be identical) |

## Quick manual-check snippet

For the items with no dedicated test (2/3, 7, 8), this pattern works against any output `.xlsx`:

```python
import openpyxl
wb = openpyxl.load_workbook('data/output/<the file>.xlsx', data_only=True)
print('Sheets:', wb.sheetnames)               # check 'cargo_flow_routes' is present (#7)

ws = wb['summary']
headers = [c.value for c in next(ws.iter_rows(min_row=1, max_row=1))]
idx = {h: i for i, h in enumerate(headers)}
for row in ws.iter_rows(min_row=2, values_only=True):
    # #8: capacity and weekly_capacity_teu should differ
    print(row[0], row[idx['capacity']], row[idx['weekly_capacity_teu']])
    # #2/#3: for a line MCTS actually modified, check waittime/mantime aren't zeroed
```

## When to run this check

After any change that touches `mcts.py`, `servicegraph.py`, `data_reader.py`, or
`output_summary.py` - not just MCTS-specific changes, since several of these items (capacity, speed
penalty, NaN handling) live in the shared MILP-building code, not the search logic.
