"""Diagnose why hard VSA operational constraints can be infeasible.

This script is intentionally arithmetic-first: it checks the same data loaded by
the MILP, then explains which VSA-only operational assumptions already
contradict the proforma route before launching a full network solve.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
	sys.path.insert(0, str(SRC))

from cma.data_reader import (  # noqa: E402
	data_file_proforma,
	read_cnc_proforma_data,
	read_port_data,
	read_sailing_distance_data,
	read_vessel_class_data,
)
from cma.port import PortGraph, PortPool  # noqa: E402
from cma.vessel import VesselPool  # noqa: E402


DEFAULT_CHECKS = [
	"rotation_loaded",
	"fixed_week",
	"fixed_rank",
	"distance_matrix",
	"min_berth_budget",
	"speed_window_discrete",
	"speed_window_continuous",
	"fixed_proforma_speed",
	"fixed_proforma_stay",
	"schedule_tether_lower_bound",
	"proforma_capacity_hint",
]


@dataclass
class CheckResult:
	line: str
	check: str
	status: str
	reason: str
	details: str = ""

	def marker(self) -> str:
		if self.status == "ok":
			return "[x]"
		if self.status == "skip":
			return "[-]"
		if self.status == "warn":
			return "[!]"
		return "[ ]"

	def as_row(self) -> dict[str, str]:
		return {
			"line": self.line,
			"check": self.check,
			"status": self.status,
			"marker": self.marker(),
			"reason": self.reason,
			"details": self.details,
		}


def _finite(value: float | int | None) -> bool:
	return value is not None and not np.isnan(value) and not np.isinf(value)


def _fmt(value: float | int | None, digits: int = 2) -> str:
	if value is None or not _finite(value):
		return "missing"
	return f"{float(value):.{digits}f}"


def _parse_week_levels(raw: str) -> list[float]:
	return [float(part.strip()) for part in raw.split(",") if part.strip()]


def _read_raw_proforma() -> pd.DataFrame:
	file = resources.files("cma.res").joinpath(data_file_proforma)
	df = pd.read_csv(file)
	return df.rename(columns=lambda x: str(x).strip())


def _vsa_raw_groups(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
	vsa = df[df["svc_type"].astype(str).str.strip().str.upper() == "VSA"]
	return {
		str(line_name): group.sort_values("sequence")
		for line_name, group in vsa.groupby("linename")
	}


def _rotation_reasons(port_ids: list[str], portpool: PortPool) -> list[str]:
	reasons: list[str] = []
	missing_ports = [port_id for port_id in port_ids if not portpool.has_port_by_id(port_id)]
	if missing_ports:
		reasons.append("missing ports: " + ", ".join(missing_ports))
		return reasons

	if len(port_ids) < 2:
		reasons.append("fewer than 2 port calls")
		return reasons

	for idx, port_id in enumerate(port_ids):
		if port_id == port_ids[(idx + 1) % len(port_ids)]:
			reasons.append(f"consecutive duplicate port: {port_id}")

	edges_seen: set[tuple[str, str]] = set()
	for idx, port_id in enumerate(port_ids):
		edge = (port_id, port_ids[(idx + 1) % len(port_ids)])
		if edge in edges_seen:
			reasons.append(f"repeated directed edge: {edge[0]}->{edge[1]}")
		edges_seen.add(edge)

	counts = {port_id: port_ids.count(port_id) for port_id in set(port_ids)}
	for port_id, count in counts.items():
		port = portpool.get_port(port_id)
		if count > port.get_max_number_of_visit():
			reasons.append(f"{port_id} visited {count} times; max is {port.get_max_number_of_visit()}")

	if len(counts) > 20:
		reasons.append(f"{len(counts)} unique ports; max is 20")

	repeated_ports = [port_id for port_id, count in counts.items() if count > 1]
	if len(repeated_ports) > 2:
		reasons.append("more than 2 repeated ports: " + ", ".join(sorted(repeated_ports)))

	if not any(portpool.get_port(port_id).transshipment_capacity for port_id in port_ids):
		reasons.append("no transshipment-capable port in rotation")

	return reasons


def _line_distance(port_ids: list[str], portgraph: PortGraph) -> tuple[float | None, list[str]]:
	total = 0.0
	missing: list[str] = []
	for idx, port_id in enumerate(port_ids):
		next_id = port_ids[(idx + 1) % len(port_ids)]
		try:
			dist = float(portgraph.get_distance_by_id(port_id, next_id))
		except ValueError:
			missing.append(f"{port_id}->{next_id}: port missing from portgraph")
			continue
		if not _finite(dist) or dist <= 0:
			missing.append(f"{port_id}->{next_id}: {_fmt(dist)} nm")
			continue
		total += dist
	return (None if missing else total), missing


def _speed_window_feasible(
	distance_nm: float | None,
	week: float | None,
	min_berth_hours: float,
	min_speed: float,
	max_speed: float,
) -> tuple[bool | None, str]:
	if distance_nm is None or week is None or not _finite(week):
		return None, "missing distance or week"
	cycle_hours = week * 168.0
	sail_budget_hours = cycle_hours - min_berth_hours
	if sail_budget_hours < 0:
		return False, (
			f"cycle {_fmt(cycle_hours)}h is below minimum berth "
			f"{_fmt(min_berth_hours)}h"
		)
	min_sailing_hours = distance_nm / max_speed
	max_sailing_hours = distance_nm / min_speed
	latest_allowed_sail = min(sail_budget_hours, max_sailing_hours)
	if min_sailing_hours <= latest_allowed_sail:
		return True, (
			f"sailing can be {_fmt(min_sailing_hours)}-{_fmt(latest_allowed_sail)}h "
			f"within cycle {_fmt(cycle_hours)}h"
		)
	return False, (
		f"needs at least {_fmt(min_sailing_hours)}h sailing at max speed, "
		f"but only {_fmt(sail_budget_hours)}h remains after min berth"
	)


def _proforma_week(df_line: pd.DataFrame) -> float | None:
	duration = df_line.iloc[0].get("duration")
	if pd.isna(duration):
		return None
	return float(duration) / 7.0


def _fixed_rank_result(
	line_name: str,
	df_line: pd.DataFrame,
	portpool: PortPool,
	vesselpool: VesselPool,
) -> CheckResult:
	rank = int(df_line.iloc[0]["vrank"])
	if rank < 1 or rank > vesselpool.get_number_of_types():
		return CheckResult(line_name, "fixed_rank", "fail", f"rank {rank} is outside vessel pool")

	missing_fit: list[str] = []
	missing_prod: list[str] = []
	missing_cost: list[str] = []
	for port_id in df_line["portid"].astype(str).tolist():
		if not portpool.has_port_by_id(port_id):
			continue
		port = portpool.get_port(port_id)
		if not port.check_is_vessel_fit(rank):
			missing_fit.append(port_id)
		if rank not in port.berth_productivity:
			missing_prod.append(port_id)
		if rank not in port.cost_portcall:
			missing_cost.append(port_id)

	if missing_fit:
		return CheckResult(
			line_name,
			"fixed_rank",
			"fail",
			f"rank {rank} is not marked fit at " + ", ".join(sorted(set(missing_fit))),
		)
	if missing_prod:
		return CheckResult(
			line_name,
			"fixed_rank",
			"warn",
			f"rank {rank} lacks productivity at " + ", ".join(sorted(set(missing_prod))),
			"the MILP falls back to gross productivity sums, but a hard VSA rank check would care",
		)
	if missing_cost:
		return CheckResult(
			line_name,
			"fixed_rank",
			"warn",
			f"rank {rank} lacks port-call cost at " + ", ".join(sorted(set(missing_cost))),
			"Port.get_portcall_costs uses a default cost, so this is not hard infeasibility",
		)
	return CheckResult(line_name, "fixed_rank", "ok", f"rank {rank} exists and fits all called ports")


def _schedule_tether_result(
	line_name: str,
	df_line: pd.DataFrame,
	port_ids: list[str],
	portgraph: PortGraph,
	distance_nm: float | None,
	week: float | None,
	max_speed: float,
	schedule_buffer_hrs: float,
) -> CheckResult:
	if distance_nm is None or week is None or not _finite(week):
		return CheckResult(line_name, "schedule_tether_lower_bound", "skip", "missing distance or week")
	if "eosp_utc_wd" not in df_line.columns or "eosp_utc_hr" not in df_line.columns:
		return CheckResult(line_name, "schedule_tether_lower_bound", "skip", "no EOSP columns")

	first = df_line.iloc[0]
	base_days = (float(first["eosp_utc_wd"]) * 24.0 + float(first["eosp_utc_hr"])) / 24.0
	total_sail_days_lb = distance_nm / (24.0 * max_speed)
	cum_dist = 0.0
	cum_min_stay_days = 0.0
	violations: list[str] = []
	rows = df_line.to_dict("records")
	leg_durations_hours = [
		float(row["time_wait"])
		+ float(row["time_manin"])
		+ float(row["staytime"])
		+ float(row["time_manout"])
		+ float(row["timetonext"])
		for row in rows
	]
	total_leg_duration = sum(leg_durations_hours)
	if total_leg_duration > 0 and week is not None:
		scale = week * 168.0 / total_leg_duration
		leg_durations_hours = [duration * scale for duration in leg_durations_hours]
	current_eosp_days = base_days

	for idx, row in enumerate(rows):
		if idx > 0:
			prev_id = port_ids[idx - 1]
			port_id = port_ids[idx]
			cum_dist += float(portgraph.get_distance_by_id(prev_id, port_id))
		frac = 0.0 if distance_nm <= 0 else cum_dist / distance_nm
		lower_bound_etb = base_days + frac * total_sail_days_lb + cum_min_stay_days

		leg_duration = leg_durations_hours[idx]
		proforma_etb = current_eosp_days + (0.2 * leg_duration) / 24.0
		upper = proforma_etb + schedule_buffer_hrs / 24.0
		if lower_bound_etb > upper + 1e-9:
			violations.append(
				f"{port_ids[idx]} lower-bound ETB {_fmt(lower_bound_etb, 3)}d > "
				f"tether upper {_fmt(upper, 3)}d"
			)
		cum_min_stay_days += 3.0 / 24.0
		current_eosp_days += leg_duration / 24.0

	if violations:
		return CheckResult(
			line_name,
			"schedule_tether_lower_bound",
			"fail",
			"; ".join(violations[:3]),
			"uses minimum sailing time and 3h per prior port call, so this is a hard contradiction",
		)
	return CheckResult(
		line_name,
		"schedule_tether_lower_bound",
		"ok",
		f"minimum-time prefix schedule fits within {schedule_buffer_hrs:g}h tether",
	)


def diagnose_line(
	line_name: str,
	df_line: pd.DataFrame,
	loaded_names: set[str],
	portpool: PortPool,
	portgraph: PortGraph,
	vesselpool: VesselPool,
	week_levels: list[float],
	schedule_buffer_hrs: float,
	checks: set[str],
) -> list[CheckResult]:
	results: list[CheckResult] = []
	port_ids = df_line["portid"].astype(str).tolist()
	week = _proforma_week(df_line)
	week_level_set = {float(w) for w in week_levels}
	distance_nm, missing_distance = _line_distance(port_ids, portgraph)
	min_berth_hours = 3.0 * len(port_ids)
	speed_levels = vesselpool.get_speed_levels()
	speed_step = float(speed_levels[1] - speed_levels[0]) if len(speed_levels) > 1 else 0.5

	if "rotation_loaded" in checks:
		reasons = _rotation_reasons(port_ids, portpool)
		if line_name not in loaded_names:
			reason = "; ".join(reasons) if reasons else "loader skipped this line"
			results.append(CheckResult(line_name, "rotation_loaded", "fail", reason))
		elif reasons:
			results.append(CheckResult(line_name, "rotation_loaded", "warn", "; ".join(reasons)))
		else:
			results.append(CheckResult(line_name, "rotation_loaded", "ok", "line is valid and loaded"))

	if "fixed_week" in checks:
		if week is None:
			results.append(CheckResult(line_name, "fixed_week", "fail", "missing proforma duration"))
		elif not math.isclose(week, round(week), abs_tol=1e-9):
			results.append(
				CheckResult(
					line_name,
					"fixed_week",
					"fail",
					f"proforma week {_fmt(week)} is non-integer",
					"ship identity requires integer vessel count",
				)
			)
		elif float(round(week)) not in week_level_set:
			results.append(
				CheckResult(
					line_name,
					"fixed_week",
					"fail",
					f"week {_fmt(week, 0)} is not in candidate week levels {week_levels}",
				)
			)
		else:
			results.append(CheckResult(line_name, "fixed_week", "ok", f"week {_fmt(week, 0)} is selectable"))

	if "fixed_rank" in checks:
		results.append(_fixed_rank_result(line_name, df_line, portpool, vesselpool))

	if "distance_matrix" in checks:
		if missing_distance:
			results.append(CheckResult(line_name, "distance_matrix", "fail", "; ".join(missing_distance[:4])))
		else:
			results.append(CheckResult(line_name, "distance_matrix", "ok", f"route distance {_fmt(distance_nm)} nm"))

	if "min_berth_budget" in checks:
		if week is None:
			results.append(CheckResult(line_name, "min_berth_budget", "skip", "missing week"))
		else:
			cycle_hours = week * 168.0
			status = "ok" if cycle_hours >= min_berth_hours else "fail"
			results.append(
				CheckResult(
					line_name,
					"min_berth_budget",
					status,
					f"cycle {_fmt(cycle_hours)}h vs minimum berth {_fmt(min_berth_hours)}h",
				)
			)

	if "speed_window_discrete" in checks:
		min_speed = float(speed_levels[0] - speed_step / 2.0)
		max_speed = float(speed_levels[-1] + speed_step / 2.0)
		ok, reason = _speed_window_feasible(distance_nm, week, min_berth_hours, min_speed, max_speed)
		results.append(
			CheckResult(
				line_name,
				"speed_window_discrete",
				"skip" if ok is None else ("ok" if ok else "fail"),
				reason,
				f"speed window {min_speed:g}-{max_speed:g} kts",
			)
		)

	if "speed_window_continuous" in checks:
		min_speed = float(speed_levels[0] - 0.5)
		max_speed = float(speed_levels[-1] + 0.5)
		ok, reason = _speed_window_feasible(distance_nm, week, min_berth_hours, min_speed, max_speed)
		results.append(
			CheckResult(
				line_name,
				"speed_window_continuous",
				"skip" if ok is None else ("ok" if ok else "fail"),
				reason,
				f"speed window {min_speed:g}-{max_speed:g} kts",
			)
		)

	if "fixed_proforma_speed" in checks:
		if distance_nm is None or week is None:
			results.append(CheckResult(line_name, "fixed_proforma_speed", "skip", "missing distance or week"))
		else:
			sail_hours = 0.0
			bad_legs: list[str] = []
			speed_values = df_line["vspeed"].astype(float).tolist()
			for idx, port_id in enumerate(port_ids):
				speed = speed_values[idx]
				next_id = port_ids[(idx + 1) % len(port_ids)]
				dist = float(portgraph.get_distance_by_id(port_id, next_id))
				if speed <= 0:
					bad_legs.append(f"{port_id}->{next_id}: speed {speed:g}")
				else:
					sail_hours += dist / speed
			remaining_stay = week * 168.0 - sail_hours
			if bad_legs:
				results.append(CheckResult(line_name, "fixed_proforma_speed", "fail", "; ".join(bad_legs[:4])))
			elif remaining_stay + 1e-9 < min_berth_hours:
				results.append(
					CheckResult(
						line_name,
						"fixed_proforma_speed",
						"fail",
						f"fixed speeds leave {_fmt(remaining_stay)}h stay, below min berth {_fmt(min_berth_hours)}h",
					)
				)
			else:
				results.append(
					CheckResult(
						line_name,
						"fixed_proforma_speed",
						"ok",
						f"fixed per-leg speeds leave {_fmt(remaining_stay)}h for stay",
					)
				)

	if "fixed_proforma_stay" in checks:
		if distance_nm is None or week is None:
			results.append(CheckResult(line_name, "fixed_proforma_stay", "skip", "missing distance or week"))
		else:
			stay_hours = float(df_line["staytime"].sum())
			sail_hours = week * 168.0 - stay_hours
			if sail_hours <= 0:
				results.append(CheckResult(line_name, "fixed_proforma_stay", "fail", "proforma stay exceeds cycle"))
			else:
				implied_speed = distance_nm / sail_hours
				min_speed = float(speed_levels[0] - speed_step / 2.0)
				max_speed = float(speed_levels[-1] + speed_step / 2.0)
				status = "ok" if min_speed <= implied_speed <= max_speed else "fail"
				results.append(
					CheckResult(
						line_name,
						"fixed_proforma_stay",
						status,
						f"fixed stay implies average speed {_fmt(implied_speed)} kts",
						f"discrete speed window {min_speed:g}-{max_speed:g} kts",
					)
				)

	if "schedule_tether_lower_bound" in checks:
		max_speed = float(speed_levels[-1] + speed_step / 2.0)
		results.append(
			_schedule_tether_result(
				line_name,
				df_line,
				port_ids,
				portgraph,
				distance_nm,
				week,
				max_speed,
				schedule_buffer_hrs,
			)
		)

	if "proforma_capacity_hint" in checks:
		rank = int(df_line.iloc[0]["vrank"])
		vessel = vesselpool.get_vessel_instance(rank)
		max_alloc = float(df_line["alloc"].max()) if "alloc" in df_line.columns else 0.0
		eff_cap = float(df_line.iloc[0].get("cap_eff", vessel.vessel_capacity))
		ref_cap = min(vessel.vessel_capacity, eff_cap)
		status = "ok" if max_alloc <= ref_cap + 1e-9 else "warn"
		results.append(
			CheckResult(
				line_name,
				"proforma_capacity_hint",
				status,
				f"max proforma alloc {_fmt(max_alloc)} TEU vs fixed-rank capacity {_fmt(ref_cap)} TEU",
				"capacity can still fail after cargo rerouting; this is only a local hint",
			)
		)

	return results


def _print_markdown(results: list[CheckResult], include_ok: bool) -> None:
	rows = results if include_ok else [r for r in results if r.status != "ok"]
	print("| line | check | status | reason | details |")
	print("| --- | --- | --- | --- | --- |")
	for result in rows:
		reason = result.reason.replace("|", "/")
		details = result.details.replace("|", "/")
		print(f"| {result.line} | {result.check} | {result.marker()} {result.status} | {reason} | {details} |")


def _write_csv(path: Path, results: Iterable[CheckResult]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	with path.open("w", newline="", encoding="utf-8") as handle:
		writer = csv.DictWriter(handle, fieldnames=["line", "check", "status", "marker", "reason", "details"])
		writer.writeheader()
		for result in results:
			writer.writerow(result.as_row())


def main() -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--line", action="append", help="Only diagnose this VSA line. Can be repeated.")
	parser.add_argument(
		"--checks",
		default=",".join(DEFAULT_CHECKS),
		help="Comma-separated checks to run, or 'all'.",
	)
	parser.add_argument(
		"--week-levels",
		default="1,2,3,4,5,6,7,8,9,10",
		help="Candidate integer week levels used by the notebook/MILP.",
	)
	parser.add_argument("--schedule-buffer-hrs", type=float, default=12.0)
	parser.add_argument("--only-problems", action="store_true", help="Hide passing checkbox rows.")
	parser.add_argument("--csv", type=Path, help="Optional CSV output path.")
	parser.add_argument("--fail-on-problems", action="store_true", help="Exit nonzero if any check fails.")
	args = parser.parse_args()

	selected_checks = set(DEFAULT_CHECKS if args.checks.strip().lower() == "all" else args.checks.split(","))
	unknown_checks = selected_checks - set(DEFAULT_CHECKS)
	if unknown_checks:
		raise ValueError("Unknown checks: " + ", ".join(sorted(unknown_checks)))

	vesselpool = read_vessel_class_data()
	portpool, _ = read_port_data()
	distance_matrix = read_sailing_distance_data(portpool)
	zero_demand = np.zeros((portpool.get_number_of_ports(), portpool.get_number_of_ports()))
	portgraph = PortGraph(portpool, distance_matrix, zero_demand, filter_by_demand=False)
	proforma = read_cnc_proforma_data(portpool, vesselpool)
	loaded_names = {line.name() for line in proforma["lines"]}
	raw_groups = _vsa_raw_groups(_read_raw_proforma())

	line_filter = set(args.line or [])
	results: list[CheckResult] = []
	for line_name in sorted(raw_groups):
		if line_filter and line_name not in line_filter:
			continue
		results.extend(
			diagnose_line(
				line_name,
				raw_groups[line_name],
				loaded_names,
				portpool,
				portgraph,
				vesselpool,
				_parse_week_levels(args.week_levels),
				args.schedule_buffer_hrs,
				selected_checks,
			)
		)

	_print_markdown(results, include_ok=not args.only_problems)
	if args.csv:
		_write_csv(args.csv, results)
		print(f"\nWrote CSV diagnostics to {args.csv}")

	failures = [result for result in results if result.status == "fail"]
	warnings = [result for result in results if result.status == "warn"]
	print(f"\nSummary: {len(failures)} failing checks, {len(warnings)} warnings across {len(set(r.line for r in results))} VSA lines.")
	return 1 if args.fail_on_problems and failures else 0


if __name__ == "__main__":
	raise SystemExit(main())
