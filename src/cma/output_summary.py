"""
MILP output-summary export helpers.

These functions consume the solved payload returned by
``ServiceGraph.fulfill_demands``. They do not enumerate paths or solve a MILP.
"""

from __future__ import annotations

import difflib
from collections import deque
from pathlib import Path
from typing import Any
import math
from uuid import uuid4

import pandas as pd
from openpyxl.cell.rich_text import CellRichText, TextBlock
from openpyxl.cell.text import InlineFont
from openpyxl.styles import PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from .port import PortGraph
from .serviceline import ServiceLine
from .vessel import VesselPool


SUMMARY_COLUMNS = [
	'linename',
	'frozen',
	'vrank',
	'capacity',
	'duration',
	'vessels',
	'ports',
	'speed',
	'seatime',
	'opstime',
	'waittime',
	'mantime',
	'cargoflow',
	'FF',
	'maxFF',
	'bunkeringcost',
	'charteringcost',
	'portcallcost',
	'transshipmentcost',
	'buffer',
	'vrank_mix',
	'speed_scope',
	'weekly_capacity_teu',
	'buffer_penalty',
	'notes',
]


def _finite_float(value: Any, default: float = 0.0) -> float:
	try:
		val = float(value)
	except (TypeError, ValueError):
		return default
	return val if math.isfinite(val) else default


def _fmt_join(values: list[Any], digits: int = 2) -> str:
	out = []
	for value in values:
		if isinstance(value, str):
			out.append(value)
			continue
		val = _finite_float(value)
		if abs(val - round(val)) < 1e-6:
			out.append(str(int(round(val))))
		else:
			out.append(f'{val:.{digits}f}')
	return '--'.join(out)


def _metadata_for_line(
		proforma_metadata: dict[str, Any] | None,
		line_name: str
	) -> dict[str, Any]:
	if not proforma_metadata:
		return {}
	return proforma_metadata.get(line_name, {}) or {}


def _dominant_rank(ship_allocation: list[float]) -> int | None:
	if not ship_allocation or max(ship_allocation) <= 1e-6:
		return None
	return int(max(range(len(ship_allocation)), key=lambda idx: ship_allocation[idx]) + 1)


def _rank_mix(ship_allocation: list[float]) -> str:
	parts = []
	for idx, count in enumerate(ship_allocation, start=1):
		if abs(count) > 1e-6:
			if abs(count - round(count)) < 1e-6:
				count_text = str(int(round(count)))
			else:
				count_text = f'{count:.2f}'
			parts.append(f'{idx}:{count_text}')
	return ';'.join(parts)


def build_milp_output_summary_dataframe(
		solution: dict[str, Any],
		service_lines: list[ServiceLine],
		portgraph: PortGraph,
		vesselpool: VesselPool,
		proforma_metadata: dict[str, Any] | None = None,
	) -> pd.DataFrame:
	"""Build a sample-output-style line summary from solved MILP diagnostics."""
	diagnostics = solution.get('line diagnostics') or []
	rows: list[dict[str, Any]] = []

	for idx_line, (line, diag) in enumerate(zip(service_lines, diagnostics)):
		line_name = line.name()
		meta = _metadata_for_line(proforma_metadata, line_name)
		port_details = meta.get('port_details') or []
		ports = line.tolist_port()
		port_ids = [port.get_id() for port in ports]
		slots = line.tolist_slot()

		selected_week = _finite_float(diag.get('selected_week'))
		selected_speed = diag.get('selected_speed_kts')
		selected_speed = None if selected_speed is None else _finite_float(selected_speed, default=float('nan'))
		weekly_capacity = _finite_float(diag.get('weekly_capacity_teu'))
		line_capacity_total = _finite_float(diag.get('line_capacity_total_teu'))
		ship_allocation = [float(x) for x in diag.get('ship_allocation', [])]

		if selected_speed is not None and math.isfinite(selected_speed) and selected_speed > 0:
			seatime = [
				slot.get_distance(portgraph) / selected_speed
				for slot in slots
			]
			speed_values = [selected_speed for _ in slots]
		else:
			seatime = [0.0 for _ in slots]
			speed_values = []

		port_stay_days = diag.get('port_stay_days') or []
		port_call_moves = diag.get('port_call_moves') or []
		dominant_rank = _dominant_rank(ship_allocation)
		def fallback_opstime_for_port(port) -> float:
			port_idx = portgraph.get_unique_index(port)
			num_visits = max(1, len(line.all_index_of_port(port)))
			stay_days = _finite_float(port_stay_days[port_idx] if port_idx < len(port_stay_days) else 0.0)
			return stay_days * 24.0 / num_visits
		def productivity_for_call(idx_call: int, port) -> float:
			if port_details and idx_call < len(port_details):
				prod = _finite_float(port_details[idx_call].get('productivity'))
				if prod > 0:
					return prod
			if dominant_rank is not None:
				prod = _finite_float(port.berth_productivity.get(dominant_rank))
				if prod > 0:
					return prod
			return 0.0

		opstime = []
		uses_routed_move_opstime = bool(port_call_moves and len(port_call_moves) == len(ports))
		if uses_routed_move_opstime:
			for idx_call, port in enumerate(ports):
				move_info = port_call_moves[idx_call] or {}
				moves = _finite_float(move_info.get('moves_teu'))
				productivity = productivity_for_call(idx_call, port)
				if productivity > 0:
					opstime.append(moves / productivity)
				else:
					opstime.append(fallback_opstime_for_port(port))
		else:
			for port in ports:
				opstime.append(fallback_opstime_for_port(port))

		if port_details:
			# CHANGE 23/08 (client feedback #2/#3 - BMX wait/man times showing 0
			# after JPYOK was added): match each of the line's CURRENT ports to its
			# proforma record by port_id, not by list position. Position-matching
			# broke as soon as MCTS added/removed/shifted a port, since the
			# proforma list's length (and order) no longer lines up with the
			# current rotation - the old code then zeroed out every port on the
			# whole line, not just the changed one. A port can be called more than
			# once in a rotation, so match occurrences in original sequence order
			# via a per-port_id queue rather than a plain dict.
			detail_queues: dict[str, deque] = {}
			for detail in sorted(port_details, key=lambda d: d.get('sequence', 0)):
				detail_queues.setdefault(detail.get('port_id'), deque()).append(detail)

			waittime = []
			mantime = []
			for port in ports:
				queue = detail_queues.get(port.get_id())
				detail = queue.popleft() if queue else None
				if detail is not None:
					waittime.append(_finite_float(detail.get('waiting_time')))
					mantime.append(
						_finite_float(detail.get('maneuvering_in')) + _finite_float(detail.get('maneuvering_out'))
					)
				else:
					# No proforma record for this port on this line (MCTS added it
					# new). Fall back to the port's own real operational data where
					# it exists (56 of 182 ports have measured wait/man times);
					# otherwise a generic placeholder, same default used elsewhere
					# in the codebase (serviceline.py's get_schedule()).
					wait_by_rank = getattr(port, 'waiting_time', None) or {}
					if dominant_rank is not None and dominant_rank in wait_by_rank:
						waittime.append(_finite_float(wait_by_rank[dominant_rank]))
					elif wait_by_rank:
						waittime.append(_finite_float(sum(wait_by_rank.values()) / len(wait_by_rank)))
					else:
						waittime.append(2.0)
					mantime.append(
						_finite_float(getattr(port, 'maneuvering_time_in', 3.0))
						+ _finite_float(getattr(port, 'maneuvering_time_out', 3.0))
					)
		else:
			wait_profile = line.get_buffer_wait_times() or [0.0 for _ in ports]
			waittime = [_finite_float(x) for x in wait_profile[:len(ports)]]
			mantime = [0.0 for _ in ports]

		segment_flows = diag.get('segment_flows') or []
		cargo_flows = [_finite_float(item.get('flow_teu')) for item in segment_flows]
		fill_factors = [
			(flow / weekly_capacity * 100.0) if weekly_capacity > 0 else 0.0
			for flow in cargo_flows
		]
		max_ff = max(fill_factors) if fill_factors else 0.0
		buffer_value = diag.get('buffer_value')
		buffer_pct = ''
		if buffer_value is not None and math.isfinite(_finite_float(buffer_value)):
			buffer_pct = f'{_finite_float(buffer_value) * 100.0:.2f}%'

		notes = ['MILP-only mod0 summary']
		if selected_speed is not None:
			notes.append('speed is line-level and repeated per segment')
		if uses_routed_move_opstime:
			notes.append('opstime from routed port moves divided by productivity')
		else:
			notes.append('opstime fallback used')
		if not port_details:
			notes.append('wait/maneuvering fallback used')

		rows.append({
			'linename': line_name,
			'frozen': meta.get('service_type', 'FIX' if line.frozen else 'OWN'),
			'vrank': _dominant_rank(ship_allocation),
			'capacity': line_capacity_total,
			'duration': selected_week * 7.0,
			'vessels': _finite_float(diag.get('vessel_count'), selected_week),
			'ports': '--'.join(port_ids),
			'speed': _fmt_join(speed_values),
			'seatime': _fmt_join(seatime),
			'opstime': _fmt_join(opstime),
			'waittime': _fmt_join(waittime),
			'mantime': _fmt_join(mantime),
			'cargoflow': _fmt_join(cargo_flows),
			'FF': _fmt_join(fill_factors),
			'maxFF': f'{max_ff:.2f}%',
			'bunkeringcost': _finite_float(diag.get('bunkering_cost')),
			'charteringcost': _finite_float(diag.get('chartering_cost')),
			'portcallcost': _finite_float(diag.get('portcall_cost')),
			'transshipmentcost': _finite_float(diag.get('transshipment_cost')),
			'buffer': buffer_pct,
			'vrank_mix': _rank_mix(ship_allocation),
			'speed_scope': 'line_level_repeated_per_segment',
			'weekly_capacity_teu': weekly_capacity,
			'buffer_penalty': _finite_float(diag.get('buffer_penalty_cost')),
			'notes': '; '.join(notes),
		})

	df = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
	if len(df) == 0:
		return df

	total_row = {col: None for col in SUMMARY_COLUMNS}
	total_row['linename'] = '__TOTAL__'
	total_row['capacity'] = df['capacity'].sum()
	total_row['duration'] = df['duration'].sum()
	total_row['vessels'] = df['vessels'].sum()
	total_row['bunkeringcost'] = df['bunkeringcost'].sum()
	total_row['charteringcost'] = df['charteringcost'].sum()
	total_row['portcallcost'] = df['portcallcost'].sum()
	total_row['transshipmentcost'] = df['transshipmentcost'].sum()
	total_row['weekly_capacity_teu'] = df['weekly_capacity_teu'].sum()
	total_row['buffer_penalty'] = df['buffer_penalty'].sum()
	total_row['notes'] = 'Column totals for numeric line-level values'
	return pd.concat([df, pd.DataFrame([total_row])], ignore_index=True)


def build_run_metadata_dataframe(solution: dict[str, Any]) -> pd.DataFrame:
	"""Build key-value run metadata for the workbook."""
	keys = [
		'total cost',
		'chartering cost',
		'transshipment cost',
		'bunkering cost',
		'portcall cost',
		'transit penalty cost',
		'unfulfilled demand penalty cost',
		'buffer penalty cost',
		'kpi_teus_input',
		'kpi_teus_fulfilled',
		'kpi_teus_delayed',
		'kpi_avg_delay_days',
		'kpi_lines_buffer_above_30',
		'kpi_lines_buffer_below_15',
		'solver_status',
		'solver_name',
		'solver_solve_time',
		'solver_mip_gap',
		'solver_best_bound',
		'solver_obj_val',
		'solver_node_count',
	]
	rows = [{'metric': key, 'value': solution.get(key)} for key in keys]
	rows.append({
		'metric': 'scenario_note',
		'value': 'MILP-only current-network summary; no MCTS modifications included.',
	})
	return pd.DataFrame(rows)


# Category label -> key in the solved-diagnostics dict (same keys used above in
# build_run_metadata_dataframe). "System" is the network's total cost.
CHANGE_SUMMARY_COST_FIELDS = [
	('Bunkering', 'bunkering cost'),
	('Chartering', 'chartering cost'),
	('Port Call', 'portcall cost'),
	('Transhipment', 'transshipment cost'),
	('System', 'total cost'),
]

def build_cargo_flow_routes_dataframe(solution: dict[str, Any]) -> pd.DataFrame:
	"""Build the per-flow, per-path cargo routing sheet (client feedback #7).

	CHANGE 18/08: the solver already computed this (`solution['cargo_flow_routes']`,
	built in ServiceGraph.fulfill_demands); it just was never written to the output
	workbook. One row per (origin, destination, path actually used).
	"""
	routes = solution.get('cargo_flow_routes') or []
	if not routes:
		return pd.DataFrame(columns=[
			'origin_port', 'destination_port', 'flow_teu',
			'num_transshipments', 'path_lines', 'path_ports',
		])
	rows = [{
		'origin_port': r['origin_port'],
		'destination_port': r['destination_port'],
		'flow_teu': r['flow_teu'],
		'num_transshipments': r['num_transshipments'],
		'path_lines': ' -> '.join(r['path_lines']),
		'path_ports': ' -> '.join(r['path_ports']),
	} for r in routes]
	df = pd.DataFrame(rows)
	return df.sort_values(['origin_port', 'destination_port', 'flow_teu'], ascending=[True, True, False])


_REMOVED_FONT = InlineFont(color='FFFF0000', strike=True)
_ADDED_FONT = InlineFont(color='FF008000')


def _line_ports_by_name(service_lines: list[ServiceLine]) -> dict[str, list[str]]:
	return {
		line.name(): [port.get_id() for port in line.tolist_port()]
		for line in service_lines
	}


def _rotation_diff_richtext(baseline_ports: list[str], best_ports: list[str]) -> CellRichText:
	"""Render one merged rotation: unchanged ports plain, ports dropped from the
	baseline struck through in red, ports added in the optimised network in green."""
	matcher = difflib.SequenceMatcher(None, baseline_ports, best_ports)
	blocks: list[Any] = []

	def add_port(port_id: str, font: InlineFont | None = None) -> None:
		if blocks:
			blocks.append(' → ')
		blocks.append(port_id if font is None else TextBlock(font, port_id))

	for tag, i1, i2, j1, j2 in matcher.get_opcodes():
		if tag == 'equal':
			for port_id in baseline_ports[i1:i2]:
				add_port(port_id)
		elif tag == 'delete':
			for port_id in baseline_ports[i1:i2]:
				add_port(port_id, _REMOVED_FONT)
		elif tag == 'insert':
			for port_id in best_ports[j1:j2]:
				add_port(port_id, _ADDED_FONT)
		elif tag == 'replace':
			for port_id in baseline_ports[i1:i2]:
				add_port(port_id, _REMOVED_FONT)
			for port_id in best_ports[j1:j2]:
				add_port(port_id, _ADDED_FONT)

	return CellRichText(*blocks)


def build_modified_lines_and_cost_delta(
		baseline_solution: dict[str, Any],
		baseline_lines: list[ServiceLine],
		best_solution: dict[str, Any],
		best_lines: list[ServiceLine],
	) -> tuple[list[tuple[str, CellRichText]], list[tuple[str, float, float, float]]]:
	"""Compare the baseline ("Simulation") and optimised ("Optimisation") networks.

	Returns:
		modified_lines: (line name, merged rotation rich text) for every line whose
			port sequence changed.
		cost_rows: (category label, simulation cost, optimisation cost, delta) for
			each category in CHANGE_SUMMARY_COST_FIELDS.
	"""
	baseline_ports_by_name = _line_ports_by_name(baseline_lines)
	best_ports_by_name = _line_ports_by_name(best_lines)

	modified_lines = []
	for name, baseline_ports in baseline_ports_by_name.items():
		best_ports = best_ports_by_name.get(name)
		if best_ports is not None and best_ports != baseline_ports:
			modified_lines.append((name, _rotation_diff_richtext(baseline_ports, best_ports)))

	cost_rows = []
	for label, key in CHANGE_SUMMARY_COST_FIELDS:
		sim_cost = _finite_float(baseline_solution.get(key))
		opt_cost = _finite_float(best_solution.get(key))
		cost_rows.append((label, sim_cost, opt_cost, opt_cost - sim_cost))

	return modified_lines, cost_rows


def write_change_summary_sheet(
		ws: Worksheet,
		modified_lines: list[tuple[str, CellRichText]],
		cost_rows: list[tuple[str, float, float, float]],
	) -> None:
	"""Write the 'lines that changed' + cost-delta-by-category layout onto ws."""
	green_fill = PatternFill(start_color='FFC6EFCE', end_color='FFC6EFCE', fill_type='solid')
	pink_fill = PatternFill(start_color='FFFFC7CE', end_color='FFFFC7CE', fill_type='solid')
	eps = 1e-6

	ws.cell(row=1, column=1, value='Lines that were modified')
	ws.cell(row=1, column=2, value='Port rotation with change')
	row = 2
	for name, rotation in modified_lines:
		ws.cell(row=row, column=1, value=name)
		ws.cell(row=row, column=2, value=rotation)
		row += 1

	header_row = row + 2
	for idx, (label, _) in enumerate(CHANGE_SUMMARY_COST_FIELDS):
		ws.cell(row=header_row, column=2 + idx, value=label)

	sim_row, opt_row, delta_row = header_row + 1, header_row + 2, header_row + 3
	ws.cell(row=sim_row, column=1, value='Simulation')
	ws.cell(row=opt_row, column=1, value='Optimisation')
	ws.cell(row=delta_row, column=1, value='Delta')

	for idx, (_, sim_cost, opt_cost, delta) in enumerate(cost_rows):
		col = 2 + idx
		ws.cell(row=sim_row, column=col, value=sim_cost)
		ws.cell(row=opt_row, column=col, value=opt_cost)
		delta_cell = ws.cell(row=delta_row, column=col, value=delta)
		if delta < -eps:
			delta_cell.fill = green_fill
		elif delta > eps:
			delta_cell.fill = pink_fill


def export_milp_output_summary(
		solution: dict[str, Any],
		service_lines: list[ServiceLine],
		portgraph: PortGraph,
		vesselpool: VesselPool,
		proforma_metadata: dict[str, Any] | None = None,
		output_path: str | Path = 'data/output/milp_output_summary.xlsx',
	) -> Path:
	"""Write the MILP output summary workbook and return its path."""
	output_path = Path(output_path)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	summary_df = build_milp_output_summary_dataframe(
		solution,
		service_lines,
		portgraph,
		vesselpool,
		proforma_metadata,
	)
	metadata_df = build_run_metadata_dataframe(solution)
	cargo_flow_routes_df = build_cargo_flow_routes_dataframe(solution)

	temp_path = output_path.with_name(
		f'.{output_path.stem}.{uuid4().hex}.tmp{output_path.suffix}'
	)
	try:
		with pd.ExcelWriter(temp_path, engine='openpyxl') as writer:
			summary_df.to_excel(writer, sheet_name='summary', index=False)
			metadata_df.to_excel(writer, sheet_name='run_metadata', index=False)
			cargo_flow_routes_df.to_excel(writer, sheet_name='cargo_flow_routes', index=False)
		try:
			temp_path.replace(output_path)
		except PermissionError as exc:
			pending_path = output_path.with_name(f'{output_path.stem}_pending{output_path.suffix}')
			try:
				temp_path.replace(pending_path)
			except Exception:
				temp_path.unlink(missing_ok=True)
				raise
			raise PermissionError(
				f'Cannot replace locked workbook "{output_path}". Close it in Excel/OneDrive preview '
				f'and rerun this cell. A complete workbook was written to "{pending_path}".'
			) from exc
	finally:
		temp_path.unlink(missing_ok=True)
	return output_path
