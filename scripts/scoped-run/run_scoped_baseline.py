"""
Solve a single baseline MILP (no MCTS search) on a *scoped subset* of the
proforma lines, and export it through the same output_summary workbook used
for full-network runs.

Why scoped: the full 31-line/182-port network is currently too slow to build
as a cvxpy problem (2+ hrs, stuck in problem construction, not the Gurobi
solve) -- see docs/progress_summary_2026-09-11.md. This script instead loads
every line named in the original client feedback (all VSA lines, all FIX
lines, plus BBX2CNC/BBX3CNC/BMXCNC/CP2CNC/YCXCNC), so the same checks the
client raised can be inspected on an output that actually finishes solving.

Usage (from repo root, using the project venv):
    .venv\\Scripts\\python.exe scripts\\scoped-run\\run_scoped_baseline.py
"""
import sys, os, time, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

ap = argparse.ArgumentParser()
ap.add_argument("--out", default=None, help="output .xlsx path")
ap.add_argument("--extra-lines", nargs="*", default=[
    "BBX2CNC", "BBX3CNC", "BMXCNC", "CP2CNC", "YCXCNC",
], help="non-VSA/FIX lines to include (named in the original client feedback)")
ap.add_argument("--mipgap", type=float, default=0.05)
ap.add_argument("--timelimit", type=int, default=300)
args = ap.parse_args()

from cma.data_reader import (read_vessel_class_data, read_port_data, read_sailing_distance_data,
    read_demand_with_transit_time, read_cnc_proforma_data)
from cma.port import PortGraph
from cma.servicegraph import ServiceGraph
from cma.output_summary import export_milp_output_summary

print("Loading data...")
vesselpool = read_vessel_class_data()
portpool_main, _ = read_port_data()
dist_matrix = read_sailing_distance_data(portpool_main)
demand_matrix, transit_time_matrix = read_demand_with_transit_time(portpool_main)
proforma = read_cnc_proforma_data(portpool_main, vesselpool, dist_matrix=dist_matrix)
all_lines = proforma["lines"]
proforma_metadata = proforma.get("metadata")

by_type = {}
for line in all_lines:
    by_type.setdefault(line.service_type, []).append(line)
print("Lines by service_type:", {k: len(v) for k, v in by_type.items()})

wanted_names = set(args.extra_lines)
scoped_lines = [
    line for line in all_lines
    if line.service_type in ("VSA", "FIX") or line.name() in wanted_names
]
print(f"Scoped network: {len(scoped_lines)} of {len(all_lines)} lines "
      f"({sum(1 for l in scoped_lines if l.service_type=='VSA')} VSA, "
      f"{sum(1 for l in scoped_lines if l.service_type=='FIX')} FIX, "
      f"{sum(1 for l in scoped_lines if l.service_type=='OWN')} OWN)")
print("Lines:", ", ".join(sorted(l.name() for l in scoped_lines)))

portgraph = PortGraph(portpool_main, dist_matrix, demand_matrix,
                      mat_transit_time=transit_time_matrix, filter_by_demand=False)
servicegraph = ServiceGraph(scoped_lines)

WEEK_LEVELS = [1, 2, 3, 4, 5, 6, 7]
TP = {'turnon-transship_shipclass_restriction': 0, 'turnon-vessel_speed_optimization': 1,
 'turnon-tight_line_capacity_linearization': 1, 'turnon-port_operations_constraint': 1,
 'turnon-transit_time_penalty': 1, 'turnon-demand_fulfillment_cap': 1, 'ctrparam-kts_buffer': 0,
 'ctrparam-transship_A': 100, 'ctrparam-speed_soft_cap_kts': 16.5, 'ctrparam-speed_penalty_multiplier': 2.0,
 'ctrparam-transit_penalty_multiplier': 1000.0, 'ctrparam-buffer_penalty_below_15pct': 1000.0,
 'ctrparam-buffer_penalty_above_30pct': 5000.0, 'unfulfilled_demand_penalty': 1e6, 'BigM-transship': 10000,
 'BigM-n_ships': 10, 'BigM-saildays': 100, 'BigM-line_capacity': 30000, 'BigM-portcall_cost': 1e7,
 'turnon-schedule_adherence': 0, 'schedule_buffer_hrs': 120.0, 'solver-MIPGap': args.mipgap,
 'solver-TimeLimit': args.timelimit, 'solver-MIPFocus': 1, 'solver-verbose': False}

print("\nSolving baseline (single MILP, no MCTS search)...")
t0 = time.time()
solution = servicegraph.solve_approximated(
    portgraph, vesselpool, min_cost=True, week_levels=WEEK_LEVELS, tuneparams_2=TP,
)
elapsed = time.time() - t0
print(f"Solved in {elapsed:.0f}s. Total cost = {servicegraph.total_cost():,.2f}")

out_path = args.out or os.path.join(ROOT, "data", "output",
    f"scoped_baseline_{time.strftime('%Y%m%d_%H%M%S')}.xlsx")
written = export_milp_output_summary(
    solution, scoped_lines, portgraph, vesselpool,
    proforma_metadata=proforma_metadata, output_path=out_path,
)
print(f"\nWorkbook written to: {written}")
