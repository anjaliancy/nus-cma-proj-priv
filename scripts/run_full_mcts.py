"""
Run full-network MCTS (all proforma lines, full demand) with per-epoch logging.

Usage (from the repo root, using the project venv):
    .venv\\Scripts\\python.exe scripts\\run_full_mcts.py
Optional overrides:
    .venv\\Scripts\\python.exe scripts\\run_full_mcts.py --epochs 30 --depth 4 --weight 0.74
    .venv\\Scripts\\python.exe scripts\\run_full_mcts.py --mipgap 0.05 --timelimit 300  # less solver noise, slower solves

Results are written to tuning_results/full_mcts_<timestamp>.log (human-readable,
one line per epoch, flushed to disk immediately) and .csv. If the run stops early
you keep every epoch that finished. Recommended first run: epochs=20, depth=3.

Also written (see docs/visualisation.md for the schema and what they feed):
    full_mcts_<timestamp>_nodes.csv  - one row per tree node, rewritten each epoch
    full_mcts_<timestamp>_tree.pkl   - pickle of the final MonteCarloTree
"""
import sys, os, argparse, random, time
from datetime import datetime
import numpy as np

# --- config (defaults = the tuning sweet spot) ---
ap = argparse.ArgumentParser()
ap.add_argument("--epochs", type=int, default=20)
ap.add_argument("--depth",  type=int, default=3)
ap.add_argument("--weight", type=float, default=0.74)   # valid_weight_proportion
ap.add_argument("--timelimit", type=int, default=120)   # per-MILP-solve seconds
ap.add_argument("--mipgap", type=float, default=0.10)    # solver-MIPGap; tighten for less run-to-run noise
ap.add_argument("--seed", type=int, default=7)
args = ap.parse_args()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
OUTDIR = os.path.join(ROOT, "tuning_results"); os.makedirs(OUTDIR, exist_ok=True)
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_PATH = os.path.join(OUTDIR, f"full_mcts_{STAMP}.log")
CSV_PATH = os.path.join(OUTDIR, f"full_mcts_{STAMP}.csv")
NODES_PATH = os.path.join(OUTDIR, f"full_mcts_{STAMP}_nodes.csv")
TREE_PATH = os.path.join(OUTDIR, f"full_mcts_{STAMP}_tree.pkl")

logf = open(LOG_PATH, "w", encoding="utf-8")
def log(msg=""):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True); logf.write(line+"\n"); logf.flush(); os.fsync(logf.fileno())
csvf = open(CSV_PATH, "w", encoding="utf-8")
csvf.write("epoch,cum_minutes,root_cost,best_cost,improvement_usd,improvement_pct,best_depth,tree_nodes\n"); csvf.flush()
def csvrow(*v):
    csvf.write(",".join(str(x) for x in v)+"\n"); csvf.flush(); os.fsync(csvf.fileno())

log(f"=== FULL-NETWORK MCTS ===  epochs={args.epochs} depth={args.depth} weight={args.weight} timelimit={args.timelimit}s mipgap={args.mipgap} seed={args.seed}")
log(f"log: {LOG_PATH}")

# epoch each node id was first seen in (node ids are path-based, so stable across epochs)
_node_first_seen: dict[str, int] = {}

def dump_nodes(tree, portgraph, epoch: int) -> None:
    """Rewrite the per-node snapshot CSV from the current tree (trees are tiny,
    so a full rewrite each epoch is cheap and crash-safe)."""
    rows = [("node_id", "parent_id", "epoch_first_seen", "depth", "action",
             "cost", "visits", "sum_value")]
    def walk(node, node_id, parent_id, depth, action_text):
        _node_first_seen.setdefault(node_id, epoch)
        try:
            cost = f"{node.graph.total_cost():.2f}"
        except Exception:
            cost = ""
        action_csv = '"' + action_text.replace("\n", " | ").replace('"', "'") + '"'
        rows.append((node_id, parent_id, _node_first_seen[node_id], depth,
                     action_csv, cost, node.number_of_visits, f"{node.sum_value:.6g}"))
        for i, child in enumerate(node.children):
            try:
                child_action = node.borns[i].explain(portgraph, node.graph, depth + 1)
            except Exception:
                child_action = str(node.borns[i])
            walk(child, f"{node_id}.{i}", node_id, depth + 1, child_action)
    walk(tree.root_node, "0", "", 0, "baseline (no changes)")
    with open(NODES_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(",".join(str(v) for v in r) for r in rows) + "\n")

from cma.data_reader import (read_vessel_class_data, read_port_data, read_sailing_distance_data,
    read_demand_with_transit_time, read_cnc_proforma_data)
from cma.port import PortGraph
from cma.servicegraph import ServiceGraph
from cma.mcts import MonteCarloTree
random.seed(args.seed); np.random.seed(args.seed)

log("Loading data...")
vesselpool = read_vessel_class_data()
portpool_main, _ = read_port_data()
dist_matrix = read_sailing_distance_data(portpool_main)
demand_matrix, transit_time_matrix = read_demand_with_transit_time(portpool_main)
proforma = read_cnc_proforma_data(portpool_main, vesselpool, dist_matrix=dist_matrix)
all_service_lines = proforma['lines']
log(f"Loaded {len(all_service_lines)} lines, {portpool_main.get_number_of_ports()} ports, "
    f"{int((np.asarray(demand_matrix)>0).sum())} OD demands")

# FULL network: all lines, full demand
portgraph = PortGraph(portpool_main, dist_matrix, demand_matrix,
                      mat_transit_time=transit_time_matrix, filter_by_demand=False)
servicegraph = ServiceGraph(all_service_lines)

WEEK_LEVELS=[1,2,3,4,5,6,7]
TP = {'turnon-transship_shipclass_restriction':0,'turnon-vessel_speed_optimization':1,
 'turnon-tight_line_capacity_linearization':1,'turnon-port_operations_constraint':1,
 'turnon-transit_time_penalty':1,'turnon-demand_fulfillment_cap':1,'ctrparam-kts_buffer':0,
 'ctrparam-transship_A':100,'ctrparam-speed_soft_cap_kts':16.5,'ctrparam-speed_penalty_multiplier':2.0,
 'ctrparam-transit_penalty_multiplier':1000.0,'ctrparam-buffer_penalty_below_15pct':1000.0,
 'ctrparam-buffer_penalty_above_30pct':5000.0,'unfulfilled_demand_penalty':1e6,'BigM-transship':10000,
 'BigM-n_ships':10,'BigM-saildays':100,'BigM-line_capacity':30000,'BigM-portcall_cost':1e7,
 'turnon-schedule_adherence':0,'schedule_buffer_hrs':120.0,'solver-MIPGap':args.mipgap,
 'solver-TimeLimit':args.timelimit,'solver-MIPFocus':1,'solver-verbose':False}

log("Solving baseline (root) ...")
t0=time.time()
servicegraph.solve_approximated(portgraph, vesselpool, min_cost=True, week_levels=WEEK_LEVELS, tuneparams_2=TP)
root_cost = servicegraph.total_cost()
log(f"Baseline root cost = {root_cost:,.2f}  (solved in {time.time()-t0:.0f}s)")

tree = MonteCarloTree(servicegraph=servicegraph, portgraph=portgraph, vesselpool=vesselpool,
    discount_fac=0.5, valid_weight_proportion=args.weight, max_depth=args.depth, c_param=1e-2,
    min_cost=True, week_levels=WEEK_LEVELS, milp_tuneparams=TP)

log("-"*70)
best_overall = root_cost
t_start=time.time()
for ep in range(1, args.epochs+1):
    te=time.time()
    try:
        tree.run(1, display=False)
        best = tree.get_best_node()
        rc = tree.root_node.graph.total_cost()
        bc = best.graph.total_cost()
        impr = rc - bc; pct = (impr/rc*100) if rc else 0.0
        best_overall = min(best_overall, bc)
        cum = (time.time()-t_start)/60
        log(f"epoch {ep:>3}/{args.epochs} | {time.time()-te:>5.0f}s (cum {cum:>5.1f}m) | "
            f"root={rc:,.0f} best={bc:,.0f} impr={impr:,.0f} ({pct:.2f}%) "
            f"depth={best.get_depth()} nodes={tree.total_number_of_nodes()}")
        csvrow(ep, f"{cum:.2f}", f"{rc:.2f}", f"{bc:.2f}", f"{impr:.2f}", f"{pct:.4f}",
               best.get_depth(), tree.total_number_of_nodes())
        try:
            dump_nodes(tree, portgraph, ep)
        except Exception as e:
            log(f"  (node snapshot failed: {e!r})")
    except Exception as e:
        log(f"epoch {ep:>3}/{args.epochs} | ERROR: {e!r}")

log("-"*70)
try:
    best = tree.get_best_node()
    log(f"FINAL: root={root_cost:,.0f}  best={best.graph.total_cost():,.0f}  "
        f"improvement={root_cost-best.graph.total_cost():,.0f} "
        f"({(root_cost-best.graph.total_cost())/root_cost*100:.2f}%)  in {(time.time()-t_start)/60:.1f} min")
    log("Best-node action trace:")
    for i, act in enumerate(best.trace_actions(), 1):
        try:
            log(f"  {i}. " + act.explain(portgraph, tree.root_node.graph, i).replace("\n", " "))
        except Exception:
            log(f"  {i}. {act}")
except Exception as e:
    log(f"final summary error: {e!r}")
try:
    tree.save_tree(TREE_PATH)
    log(f"tree pickle saved: {TREE_PATH}")
except Exception as e:
    log(f"tree pickle failed: {e!r}")
log("=== done ===")
logf.close(); csvf.close()
