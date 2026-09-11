"""
Export the best network found by a full-network MCTS run into the standard
MILP output-summary workbook format (same format/columns used elsewhere for
the visualisation), so it can be reviewed/loaded like any other solved network.

Usage (from repo root, using the project venv):
    .venv\\Scripts\\python.exe scripts\\export_mcts_best_network.py \
        --tree tuning_results\\full_mcts_20260712_220442_tree.pkl \
        --out data\\output\\mcts_best_20260712_220442_output_summary.xlsx

Loads the pickled MonteCarloTree (which carries its own portgraph/vesselpool/
tuneparams), pulls out the best-cost node's ServiceGraph, re-solves it once
more to recover the full MILP diagnostics (the tree only keeps the scalar
cost per node, not the solve diagnostics), then writes the workbook via
`cma.output_summary.export_milp_output_summary` -- the same helper used for
the baseline (current-network) summary.
"""
import sys, os, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

ap = argparse.ArgumentParser()
ap.add_argument("--tree", required=True, help="path to a full_mcts_<stamp>_tree.pkl file")
ap.add_argument("--out", default=None, help="output .xlsx path (default: data/output/mcts_best_<stamp>_output_summary.xlsx)")
args = ap.parse_args()

from cma.mcts import MonteCarloTree
from cma.data_reader import read_vessel_class_data, read_port_data, read_sailing_distance_data, read_cnc_proforma_data
from cma.output_summary import export_milp_output_summary

print(f"Loading tree: {args.tree}")
tree = MonteCarloTree.load_tree(args.tree)
if tree is None:
    raise SystemExit(f"Could not load tree from {args.tree}")

portgraph = tree.portgraph
vesselpool = tree.vesselpool
week_levels = tree.week_levels
tuneparams = tree.milp_tuneparams

root_cost = tree.root_node.graph.total_cost()
best = tree.get_best_node()
best_cost = best.graph.total_cost()
print(f"root cost = {root_cost:,.2f}")
print(f"best cost = {best_cost:,.2f}  (improvement {root_cost - best_cost:,.2f}, "
      f"{(root_cost - best_cost) / root_cost * 100:.2f}%)")
print("Best-node action trace:")
for i, act in enumerate(best.trace_actions(), 1):
    print(f"  {i}. " + act.explain(portgraph, tree.root_node.graph, i).replace("\n", " "))

# The tree only stores the scalar cost per node; re-solve the best network once
# more to recover the full MILP diagnostics dict needed for the output summary.
print("\nRe-solving best network to recover MILP diagnostics ...")
solution = best.graph.solve_approximated(
    portgraph, vesselpool,
    min_cost=True,
    week_levels=week_levels,
    tuneparams_2=tuneparams,
)
resolved_cost = best.graph.total_cost()
print(f"Re-solved cost = {resolved_cost:,.2f} (diagnostics captured)")

print("Re-solving baseline (root) network to recover its diagnostics for the changes sheet ...")
baseline_solution = tree.root_node.graph.solve_approximated(
    portgraph, vesselpool,
    min_cost=True,
    week_levels=week_levels,
    tuneparams_2=tuneparams,
)
baseline_service_lines = tree.root_node.graph.tolist_serviceLine()

print("Reloading proforma metadata (for port_details / speed lookups) ...")
vesselpool_for_meta = read_vessel_class_data()
portpool_main, _ = read_port_data()
dist_matrix = read_sailing_distance_data(portpool_main)
proforma = read_cnc_proforma_data(portpool_main, vesselpool_for_meta, dist_matrix=dist_matrix)
proforma_metadata = proforma.get("metadata")

service_lines = best.graph.tolist_serviceLine()

out_path = args.out
if out_path is None:
    stamp = os.path.basename(args.tree).replace("full_mcts_", "").replace("_tree.pkl", "")
    out_path = os.path.join(ROOT, "data", "output", f"mcts_best_{stamp}_output_summary.xlsx")

written = export_milp_output_summary(
    solution,
    service_lines,
    portgraph,
    vesselpool,
    proforma_metadata=proforma_metadata,
    output_path=out_path,
)

# Patch the run_metadata sheet: the default scenario_note is baseline-only
# boilerplate ("no MCTS modifications included"), and the tree only stores
# the scalar cost per node (not diagnostics), so its logged improvement can
# differ from what a fresh solve of the same network lands on within the MIP
# gap. Record both numbers plus the action trace so the workbook is self-
# explanatory instead of silently overwriting the log's headline figure.
import pandas as pd
import openpyxl

action_trace = ' | '.join(
    act.explain(portgraph, tree.root_node.graph, i).replace("\n", " ")
    for i, act in enumerate(best.trace_actions(), 1)
)
tree_pct = (root_cost - best_cost) / root_cost * 100
resolved_pct = (root_cost - resolved_cost) / root_cost * 100

summary_df = pd.read_excel(written, sheet_name='summary')
metadata_df = pd.read_excel(written, sheet_name='run_metadata')
metadata_df.loc[metadata_df['metric'] == 'scenario_note', 'value'] = (
    'MCTS best-network summary: baseline + the 3 MCTS-selected edits below, '
    'diagnostics from a fresh MILP re-solve of this network.'
)
extra_rows = pd.DataFrame([
    {'metric': 'mcts_source_tree', 'value': os.path.abspath(args.tree)},
    {'metric': 'mcts_root_cost', 'value': root_cost},
    {'metric': 'mcts_tree_best_cost', 'value': best_cost},
    {'metric': 'mcts_tree_reported_improvement_pct', 'value': round(tree_pct, 2)},
    {'metric': 'resolved_cost_used_in_this_summary', 'value': resolved_cost},
    {'metric': 'resolved_actual_improvement_pct', 'value': round(resolved_pct, 2)},
    {'metric': 'note_on_discrepancy', 'value': (
        "Tree-logged improvement and the re-solved improvement differ because MCTS "
        "only records the scalar MILP cost per node; re-solving the same network "
        "picks a different feasible point within the solver's MIP gap. See "
        "docs/visualisation.md section 5."
    )},
    {'metric': 'mcts_action_trace', 'value': action_trace},
])
metadata_df = pd.concat([metadata_df, extra_rows], ignore_index=True)

with pd.ExcelWriter(written, engine='openpyxl') as writer:
    summary_df.to_excel(writer, sheet_name='summary', index=False)
    metadata_df.to_excel(writer, sheet_name='run_metadata', index=False)

# Add the "what changed" sheet: modified line rotations (baseline vs best, diffed)
# plus a Simulation/Optimisation/Delta cost table by category. Done as a separate
# openpyxl pass since the pandas ExcelWriter above rewrites the whole file and
# doesn't support the rich-text (colored/struck-through) cells this sheet needs.
from cma.output_summary import build_modified_lines_and_cost_delta, write_change_summary_sheet

modified_lines, cost_rows = build_modified_lines_and_cost_delta(
    baseline_solution, baseline_service_lines,
    solution, service_lines,
)
wb = openpyxl.load_workbook(written)
if 'changes' in wb.sheetnames:
    del wb['changes']
write_change_summary_sheet(wb.create_sheet('changes'), modified_lines, cost_rows)
wb.save(written)

print(f"\nMCTS best-network output summary written to: {written}")
print(f"NOTE: tree log reported {tree_pct:.2f}% improvement; a fresh re-solve of the "
      f"same network (used for this workbook's diagnostics) lands at {resolved_pct:.2f}% "
      f"due to MIP-gap solver noise. Both numbers are recorded in the run_metadata sheet.")
