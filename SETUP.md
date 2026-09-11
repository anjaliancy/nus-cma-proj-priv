# Setting up this project from scratch

Steps to get a working copy of the CMA project on a new machine.

## 1. Get the code

```
git clone https://github.com/nuscma/nus_cma_project.git
cd nus_cma_project
git checkout reorg-structure
```

(Swap the branch name if you're picking up different work.)

## 2. Python environment

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install -e .
```

The `pip install -e .` step installs the `cma` package (see `pyproject.toml`) in
editable mode, so notebooks and scripts can `import cma` without any `sys.path`
hacks.

**Note:** `requirements.txt` does not include everything the project actually
uses — `gurobipy` (the solver), `streamlit` and `plotly` (the dashboard) were
installed ad hoc and never added to the file. Also install:

```
.venv\Scripts\pip install gurobipy streamlit plotly
```

## 3. Gurobi license

The MILP solver needs a Gurobi WLS academic license.

- Copy your existing `gurobi.lic` file to the new machine's home directory
  (e.g. `C:\Users\<you>\gurobi.lic`).
- WLS licenses are sometimes tied to a machine ID — if it doesn't activate,
  request/regenerate one from the Gurobi academic WLS portal.

## 4. Data

Copy the `data/` folder from your old machine. It's gitignored (not in the
repo) and required — inputs, benchmarks, and any output workbooks you want to
keep live there. It's roughly 50+ MB.

## 5. Gitignored docs (optional)

A few plain-language / working docs are intentionally kept out of git (see
`.gitignore`): `CONCEPT.md`, `EASY_UNDERSTAND.md`, `FULL_RUN_RESULTS.md`,
`WEEKEND_SUMMARY*.md`, and some `docs/*.md` files. Copy these over from your
old machine if you want that context — they aren't required to run anything.

## 6. Sanity check

```
.venv\Scripts\python.exe -c "import gurobipy, cma; print('ok')"
.venv\Scripts\python.exe -m streamlit run scripts\dashboard.py
```

The first command confirms the solver and the `cma` package both import. The
second launches the results dashboard — if it opens in your browser without
errors, the setup is complete.

## 7. Running a full MCTS search (optional)

```
.venv\Scripts\python.exe scripts\run_full_mcts.py
```

See `docs/visualisation.md` for what each run produces and how it feeds the
dashboard.
