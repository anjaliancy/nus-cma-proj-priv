#!/bin/bash
# Runs the 4 targeted hyperparameter combos from sweep_full_mcts.py through
# run_full_mcts.py (so each run gets its own log/csv/nodes-csv/tree-pkl for
# the visualisation dashboard), sequentially, same seed for comparability.
set -u
cd "$(dirname "$0")/.."
PY=".venv/Scripts/python.exe"
SEED=7
SUMMARY="tuning_results/batch_summary_$(date +%Y%m%d_%H%M%S).log"
mkdir -p tuning_results
echo "=== batch started $(date) ===" | tee -a "$SUMMARY"

run_combo () {
  local epochs=$1 depth=$2 weight=$3
  echo "" | tee -a "$SUMMARY"
  echo "--- combo: epochs=$epochs depth=$depth weight=$weight seed=$SEED ---" | tee -a "$SUMMARY"
  local t0=$(date +%s)
  "$PY" scripts/run_full_mcts.py --epochs "$epochs" --depth "$depth" --weight "$weight" --seed "$SEED" \
    >> "$SUMMARY" 2>&1
  local rc=$?
  local t1=$(date +%s)
  echo "--- combo done (exit=$rc, $(( (t1-t0)/60 ))m) ---" | tee -a "$SUMMARY"
}

run_combo 40 2 0.74
run_combo 40 3 0.74
run_combo 40 4 0.74
run_combo 40 3 0.85

echo "" | tee -a "$SUMMARY"
echo "=== batch finished $(date) ===" | tee -a "$SUMMARY"
