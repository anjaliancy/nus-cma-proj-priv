"""
Small hyperparameter sweep on the FULL network (all proforma lines, full demand),
mirroring src/tune_mcts_hyperparams.ipynb but scaled down (fewer combos, fewer
epochs per combo) since full-network MILP solves are much slower than the
8-line smoke test the notebook uses.

Usage (from the repo root, using the project venv):
    .venv\\Scripts\\python.exe scripts\\sweep_full_mcts.py

Writes tuning_results/mcts_tuning_<timestamp>.csv in the same schema the
dashboard's "Hyperparameter sweep" tab already reads (idx,epochs,max_depth,
valid_weight,wall_time_s,root_cost,best_cost,improvement_usd,improvement_pct,
tree_nodes,status,note), plus a matching .log with progress.
"""
import sys, os, time
from datetime import datetime
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
OUTDIR = os.path.join(ROOT, "tuning_results"); os.makedirs(OUTDIR, exist_ok=True)
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = os.path.join(OUTDIR, f"mcts_tuning_{STAMP}.log")
CSV_PATH = os.path.join(OUTDIR, f"mcts_tuning_{STAMP}.csv")

logf = open(LOG_PATH, "w", encoding="utf-8")
def log(msg=""):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True); logf.write(line+"\n"); logf.flush(); os.fsync(logf.fileno())

csvf = open(CSV_PATH, "w", encoding="utf-8")
csvf.write("idx,epochs,max_depth,valid_weight,wall_time_s,root_cost,best_cost,improvement_usd,improvement_pct,tree_nodes,status,note\n")
csvf.flush()
def csvrow(*v):
    csvf.write(",".join(str(x) for x in v)+"\n"); csvf.flush(); os.fsync(csvf.fileno())

# Small, targeted grid: hold weight at the known sweet spot (0.74) while probing
# depth 2-4, plus one check at weight 0.85 to see if the smoke-test finding
# (0.85 sometimes beats 0.74) transfers to the full network.
COMBOS = [
    (10, 2, 0.74),
    (10, 3, 0.74),
    (10, 4, 0.74),
    (10, 3, 0.85),
]
EPOCHS_SHARED = None  # epochs set per-combo above

log(f"=== FULL-NETWORK HYPERPARAMETER SWEEP === {len(COMBOS)} combos: {COMBOS}")
log(f"log: {LOG_PATH}  csv: {CSV_PATH}")

from cma.data_reader import (read_vessel_class_data, read_port_data, read_sailing_distance_data,
    read_demand_with_transit_time, read_cnc_proforma_data)
from cma.port import PortGraph
from cma.servicegraph import ServiceGraph
from cma.mcts import MonteCarloTree
import random
random.seed(7); np.random.seed(7)

log("Loading data...")
vesselpool = read_vessel_class_data()
portpool_main, _ = read_port_data()
dist_matrix = read_sailing_distance_data(portpool_main)
demand_matrix, transit_time_matrix = read_demand_with_transit_time(portpool_main)
proforma = read_cnc_proforma_data(portpool_main, vesselpool, dist_matrix=dist_matrix)
all_service_lines = proforma['lines']
log(f"Loaded {len(all_service_lines)} lines, {portpool_main.get_number_of_ports()} ports, "
    f"{int((np.asarray(demand_matrix)>0).sum())} OD demands")

portgraph = PortGraph(portpool_main, dist_matrix, demand_matrix,
                      mat_transit_time=transit_time_matrix, filter_by_demand=False)

WEEK_LEVELS=[1,2,3,4,5,6,7]
TP = {'turnon-transship_shipclass_restriction':0,'turnon-vessel_speed_optimization':1,
 'turnon-tight_line_capacity_linearization':1,'turnon-port_operations_constraint':1,
 'turnon-transit_time_penalty':1,'turnon-demand_fulfillment_cap':1,'ctrparam-kts_buffer':0,
 'ctrparam-transship_A':100,'ctrparam-speed_soft_cap_kts':16.5,'ctrparam-speed_penalty_multiplier':2.0,
 'ctrparam-transit_penalty_multiplier':1000.0,'ctrparam-buffer_penalty_below_15pct':1000.0,
 'ctrparam-buffer_penalty_above_30pct':5000.0,'unfulfilled_demand_penalty':1e6,'BigM-transship':10000,
 'BigM-n_ships':10,'BigM-saildays':100,'BigM-line_capacity':30000,'BigM-portcall_cost':1e7,
 'turnon-schedule_adherence':0,'schedule_buffer_hrs':120.0,'solver-MIPGap':0.10,
 'solver-TimeLimit':120,'solver-MIPFocus':1,'solver-verbose':False}

log("-"*70)
t_sweep = time.time()
for idx, (epochs, max_depth, weight) in enumerate(COMBOS, 1):
    log(f"[{idx}/{len(COMBOS)}] epochs={epochs} depth={max_depth} weight={weight}")
    t0 = time.time()
    try:
        servicegraph = ServiceGraph(all_service_lines)
        servicegraph.solve_approximated(portgraph, vesselpool, min_cost=True,
                                         week_levels=WEEK_LEVELS, tuneparams_2=TP)
        root_cost = servicegraph.total_cost()
        log(f"  baseline solved: root_cost={root_cost:,.2f} ({time.time()-t0:.0f}s)")

        tree = MonteCarloTree(servicegraph=servicegraph, portgraph=portgraph, vesselpool=vesselpool,
            discount_fac=0.5, valid_weight_proportion=weight, max_depth=max_depth, c_param=1e-2,
            min_cost=True, week_levels=WEEK_LEVELS, milp_tuneparams=TP)
        tree.run(epochs, display=False)
        elapsed = time.time() - t0

        best = tree.get_best_node()
        best_cost = best.graph.total_cost()
        impr = root_cost - best_cost
        pct = (impr/root_cost*100) if root_cost else 0.0
        nodes = tree.total_number_of_nodes()

        log(f"  done: wall={elapsed:.0f}s best={best_cost:,.0f} impr={impr:,.0f} ({pct:.2f}%) nodes={nodes}")
        csvrow(idx, epochs, max_depth, weight, f"{elapsed:.1f}", f"{root_cost:.2f}",
               f"{best_cost:.2f}", f"{impr:.2f}", f"{pct:.4f}", nodes, "ok", "")
    except Exception as e:
        elapsed = time.time() - t0
        log(f"  ERROR: {e!r}")
        csvrow(idx, epochs, max_depth, weight, f"{elapsed:.1f}", "", "", "", "", "", "error", str(e).replace(",", ";"))

log("-"*70)
log(f"=== sweep done in {(time.time()-t_sweep)/60:.1f} min ===")
logf.close(); csvf.close()
