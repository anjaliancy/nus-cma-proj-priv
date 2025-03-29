"""
Module `servicegraph`

Define all service graph related classes and methods
"""

# from __future__ import annotations  # For Python < 3.11
import typing
from typing import Literal
import time
import math
import bisect
import cvxpy as cp
import numpy as np
import pandas as pd
import geopandas as gpd
import statsmodels.api as sm

from statsmodels.regression.linear_model import RegressionResultsWrapper
from scgraph.geographs.marnet import marnet_geograph  # type: ignore
from shapely.geometry import LineString, Point

from .vessel import VesselPool
from .port import Port, PortGraph, PortPool
from .serviceline import ServiceLine, LineAction, Path, Slot, Segment
from .rl_utils import MatrixAnalyzer


class GraphAction:
	"""This class defines the class of action that adjust the graph of servicelines

	The action looks like: ('line ID', 'add'/'delete', locs)
	"""
	idx_line: int
	cmd: Literal['add', 'delete']
	loc: list[int]

	def __init__(self, idx_line: int, cmd: Literal['add', 'delete'], loc: list[int]):
		self.idx_line = idx_line
		self.cmd = cmd
		self.loc = loc

	def __repr__(self) -> str:
		return str([self.idx_line, self.cmd, self.loc])

	def __eq__(self, other) -> bool:
		# if self.line != other.line:
		# 	return False
		# if self.cmd != other.cmd:
		# 	return False
		# if self.loc != other.loc:
		# 	return False
		# return True
		return self.idx_line == other.idx_line and self.cmd == other.cmd and self.loc == other.loc

	def get_line_action(self, serviceline: ServiceLine, portgraph: PortGraph) -> LineAction:
		return LineAction(self.cmd, self.loc)

	def explain(self, portgraph: PortGraph, servicegraph: 'ServiceGraph', action_number:int|None=None) -> str:
		lines = servicegraph.tolist_serviceLine()
		if action_number is None:
			re: str = 'Action:\n'
		else:
			re: str = f'Action {action_number}:\n'
		re += f'    For the #{self.idx_line} line "{lines[self.idx_line]}",\n'
		start_idx, end_idx, idx_port = self.loc[0], self.loc[1], self.loc[2]
		start = portgraph.get_port_by_idx(start_idx)
		end = portgraph.get_port_by_idx(end_idx)
		port = portgraph.get_port_by_idx(idx_port)
		match self.cmd:
			case 'add':
				re += f'    Add Port "{port}" in the segment {start, end}.'
			case 'delete':
				re += f'    Delete Port "{port}" in the two ports "{start}" and "{end}".'
		return re

# region - Predict Weeks
#
def _extract_line(line: ServiceLine, portgraph: PortGraph):
	"""
	Make sure that `line` is not empty
	"""
	inflows, outflows = portgraph.get_demand_flows()
	current_lines_sailing_distance = line.get_distance(portgraph)
	current_lines_stops_number = line.number_of_port()
	sum_prods = 0
	sum_inflows = 0
	sum_outflows = 0
	for p in line.tolist_port():
			sum_inflows += inflows[portgraph.get_unique_index(p)]
			sum_outflows += outflows[portgraph.get_unique_index(p)]
			sum_prods += sum(p.berth_productivity)
	current_lines_ave_productivity = sum_prods / line.number_of_port()
	current_lines_ave_demandinflow = sum_inflows / line.number_of_port()
	current_lines_ave_demandoutflow = sum_outflows / line.number_of_port()
	return {
		'const': 1.0,
		'weeks': line.week,
		'sailing_distance': current_lines_sailing_distance,
		'stops_number': current_lines_stops_number,
		'ave_productivity': current_lines_ave_productivity,
		'ave_demand_inflows': current_lines_ave_demandinflow,
		'ave_demand_outflows': current_lines_ave_demandoutflow
	}

def _extract_lines(lines: list[ServiceLine], portgraph: PortGraph) -> pd.DataFrame:
	"""
	Make sure that each line in `lines` is not empty
	"""
	df = pd.DataFrame()
	for line in lines:
		rec = _extract_line(line, portgraph)
		df_new = pd.DataFrame([rec])
		df = pd.concat([df, df_new], ignore_index=True)
	return df

def update_week_predictor(df: pd.DataFrame, lines: list[ServiceLine], portgraph: PortGraph
						) -> tuple[RegressionResultsWrapper, pd.DataFrame]:
	# update old `df`
	new_row = _extract_lines(lines, portgraph)
	df = pd.concat([df, new_row], ignore_index=True)
	# run OLS
	xs = df.drop(columns=['weeks'])
	y = df['weeks']
	model = sm.OLS(y, xs).fit()
	return model, df

def apply_prediction(model: RegressionResultsWrapper,
		lines: list[ServiceLine], portgraph: PortGraph,
	) -> np.ndarray:
	predicts = []
	for line in lines:
		if line.number_of_port() == 0:
			predicts.append(0.0)
			continue
		df = _extract_lines([line], portgraph)
		xs = df.drop(columns=['weeks'])
		predict = model.predict(xs)[0]
		if predict < 3/4:
			predict = 1/2
		elif predict > 9:
			predict = 9
		else:
			predict = round(predict)
		predicts.append(predict)
	return np.array(predicts)
#
# endregion

class ServiceGraph:
	"""The graph of the service system
	"""
	__lines_list: list[ServiceLine]
	__total_cost: float

	def __init__(self, services: list[ServiceLine]):
		self.__lines_list = services
		self.__total_cost = math.inf

	def __repr__(self) -> str:
		# re = ''
		# for line in self.__lines_list:
		# 	re += str(line) + '\n'
		# return re
		return ''.join(str(line) + '\n' for line in self.__lines_list)

	def plot(self, lines_info: list[tuple[str, str]],
			selected_countries: list[str], portgraph: PortGraph,
			params_background = {
				'plot_port_id': False,
				'display_info':False,
				'demandtype': 'total',
				'odpairs': False,
				'odpairs_color': 'red'
			}
		):
		_, ax, _ = portgraph.plot(
				selected_countries,
				params_background['plot_port_id'],
				params_background['display_info'],
				params_background['demandtype'],
				params_background['odpairs'],
				params_background['odpairs_color'])
		lines: list[ServiceLine] = []
		lines_color: list[str] = []
		all_lines_id = [l.name() for l in self.__lines_list]
		for line_info in lines_info:
			line_id, line_color = line_info
			if line_id in all_lines_id:
				idx_line = all_lines_id.index(line_id)
				lines.append(self.__lines_list[idx_line])
				lines_color.append(line_color)
		# plot lines
		for idx_line, line in enumerate(lines):
			slots = line.tolist_slot()
			for idx, slot in enumerate(slots):
				p1 = slot.get_start()
				p2 = slot.get_end()
				loc_1 = p1.get_location()
				loc_2 = p2.get_location()
				output = marnet_geograph.get_shortest_path(
					origin_node={"longitude": loc_1[0],"latitude": loc_1[1]},      # type: ignore
					destination_node={"longitude": loc_2[0],"latitude": loc_2[1]}  # type: ignore
				)
				cords_path = output['coordinate_path']
				path = LineString([(cord[1], cord[0]) for cord in cords_path])
				gdf_path = gpd.GeoDataFrame({'geometry': [path]})
				label = f'({idx+1}->{line.idx_of_next_idx(idx) + 1}): ' \
					+ str(p1) + '->' + str(p2)
				gdf_path.plot(ax=ax, linewidth=2, label = label, color=lines_color[idx_line])

# region - Basic Attributes & Operations ########################################
#
	def total_cost(self) -> float:
		return self.__total_cost

	def tolist_serviceLine(self) -> list[ServiceLine]:
		return self.__lines_list

	def slotize(self) -> tuple[list[Segment], list[list[Slot]]]:
		"""
		Return two objects:
			1. Segment Union: list[Segment]
			2. Slot list of each service: list[list[Slot]]
		"""
		all_service_slots = []
		seg_union = set()
		for service_i in self.__lines_list:
			service_i_slots = service_i.tolist_slot()
			all_service_slots.append(service_i_slots)
			for slot in service_i_slots:
				seg_union.add(slot.get_segment())
		return list(seg_union), all_service_slots

	def get_adjacency_matrices(self, portgraph: PortGraph) -> list[np.ndarray]:
		returned_adjs: list[np.ndarray] = []
		returned_adjs.extend(line.get_adjacency_matrix(portgraph) for line in self.__lines_list)
		return returned_adjs

	def add_servicelines(self, newlines: list[ServiceLine]):
		for l in newlines:
			if l not in self.__lines_list:
				self.__lines_list.append(l)
#
# endregion

# region - Actions related ######################################################
#
	def update_by_graph_action(self, graph_action: GraphAction, portgraph: PortGraph) -> 'ServiceGraph':
		old_line = self.__lines_list[graph_action.idx_line]
		line_action = graph_action.get_line_action(old_line, portgraph)
		new_line = old_line.apply_action(line_action, portgraph)

		new_services: list[ServiceLine] = self.__lines_list.copy()
		new_services[graph_action.idx_line] = new_line
		return ServiceGraph(new_services)

	def get_feasible_actions(self, portgraph: PortGraph):
		analyzer = MatrixAnalyzer(self.get_adjacency_matrices(portgraph))
		actions_dict = analyzer.find_valid_k(portgraph)
		actions_list = [
			GraphAction(line_key, action_key, action)
			for line_key, line_actions in actions_dict.items()
			for action_key, actions in line_actions.items()
			for action in actions
		]
		return actions_dict, actions_list
#
# endregion

# region - Path related #########################################################
#
	def get_isolated_ports(self, portgraph: PortGraph) -> list[Port]:
		connected_ports = set()
		for line in self.__lines_list:
			line_ports = set(line.tolist_port())
			connected_ports = connected_ports.union(line_ports)
		fullports = set(portgraph.tolist_port())
		return list(fullports.difference(connected_ports))

	def get_all_lines_contains(self, ports: list[Port]) -> list[ServiceLine]:
		re = set()
		for line in self.__lines_list:
			for port in ports:
				if line.has_port(port):
					re.add(line)
		return list(re)

	def get_paths(self, start: Port, end: Port, trans_ports) -> list[Path]:
		"""Find out all paths that connects an OD pair

		Note: this method allows transshipment only for once atmost
		"""
		paths_list: list[Path] = []
		lines_has_o: list[ServiceLine] = self.get_all_lines_contains([start])
		lines_has_d: list[ServiceLine] = self.get_all_lines_contains([end])
		for line_o in lines_has_o:
			for line_d in lines_has_d:
				# case 1:
				if line_o == line_d:
					paths_list.append(line_o.get_shortest_path(start, end))
					break  # if there is a line connects od directly
				# case 2:
				hubs = list(set(line_o.tolist_port()) & set(line_d.tolist_port()))
				if not hubs:  # len(hubs) == 0
					continue
				for hub in hubs:
					if hub not in trans_ports:
						continue
					# print(line_o.name(), line_d.name(), hub)
					path_1, path_2 = [], []
					if start != hub:
						path_1 = line_o.get_shortest_path(start, hub).tolist_slot()
					if hub != end:
						path_2 = line_d.get_shortest_path(hub, end).tolist_slot()
					if len(path_1) + len(path_2) > 0:
						paths_list.append(Path(path_1 + path_2))
		return paths_list

	def get_paths_2(self, start: Port, end: Port, trans_ports) -> list[Path]:
		"""Find out all paths the connects an OD pair

		Note: this method finds all path with 2 transshipments
		"""
		paths_list: list[Path] = []
		lines_has_o: list[ServiceLine] = self.get_all_lines_contains([start])
		lines_has_d: list[ServiceLine] = self.get_all_lines_contains([end])

		for line_mid in self.__lines_list:
			for line_o in lines_has_o:
				if line_o == line_mid:
					continue
				hubs_o_mid = list(set(line_o.tolist_port()) & set(line_mid.tolist_port()))
				if not hubs_o_mid:
					continue  # to another line_o
				for line_d in lines_has_d:
					if line_d == line_mid:
						continue
					hubs_mid_d = list(set(line_d.tolist_port()) & set(line_mid.tolist_port()))
					if not hubs_mid_d:
						continue # to another line_d
					for hub1 in hubs_o_mid:
						if hub1 not in trans_ports:
							continue
						for hub2 in hubs_mid_d:
							if hub2 not in trans_ports:
								continue
							path1, path2, path3 = [], [], []
							if start != hub1:
								path1 = line_o.get_shortest_path(start, hub1).tolist_slot()
							if hub1 != hub2:
								path2 = line_mid.get_shortest_path(hub1, hub2).tolist_slot()
							if hub2 != end:
								path3 = line_d.get_shortest_path(hub2, end).tolist_slot()
							if len(path1) + len(path2) + len(path3) > 0:
								paths_list.append(Path(path1 + path2 + path3))
		return paths_list

	def get_all_paths(self, portgraph: PortGraph, trans_ports: None|list[Port]=None) -> dict[str, list]:
		"""Searching all connected paths among all ports in the network

		input:
			`trans_ports`: hubs for transshipment

		Note: this method allows transshipment only for twice atmost

		return:
			`od_pairs`: list of port-index pairs (ports are 0 indexed)
			`od_pairs_path`: for each OD pair, there is a list of path
			`od_pairs_demand`: list of demand between OD pairs (sorted from large to small)
			`unconnected`: all unconnected OD pairs
		"""
		if trans_ports is None:
			trans_ports = portgraph.filtered_by_transship_capacity()
		od_pairs: list[tuple[int, int]] = portgraph.get_all_od_pairs()
		paths: list[list[Path]] = []
		connected: list[tuple[int, int]] = []
		unconnected: list[tuple[int, int]] = []
		unconnected_demand: list[float] = []
		od_pairs_demand: list[float] = []

		for pair in od_pairs:
			pair_demand = portgraph.get_demand_by_idx(pair[0], pair[1])
			pair_loc = bisect.bisect(od_pairs_demand, pair_demand)
			bisect.insort(od_pairs_demand, pair_demand)
			port_o = portgraph.get_port_by_idx(pair[0])
			port_d = portgraph.get_port_by_idx(pair[1])
			paths_od = self.get_paths(port_o, port_d, trans_ports)
			if len(paths_od) > 0:
				paths.insert(pair_loc, paths_od)
				connected.insert(pair_loc, pair)
			else:
				# try 2 transshipments
				paths_od: list[Path] = self.get_paths_2(port_o, port_d, trans_ports)
				if len(paths_od) > 0:
					paths.insert(pair_loc, paths_od)
					connected.insert(pair_loc, pair)
				else:
					unconnected.append(pair)
					unconnected_demand.append(pair_demand)

		connected.reverse()
		paths.reverse()
		od_pairs_demand.reverse()
		return {
			'od_pairs': connected,
			'od_pairs_path': paths,
			'od_pairs_demand': od_pairs_demand,
			'unconnected': unconnected,
			'unconnected_demand': unconnected_demand
		}
#
# endregion

# region Key method: solve the minimum cost #####################################
#
	def solve_approximated_cost(self, portgraph: PortGraph, vesselpool: VesselPool,
			week_levels = (1/2, 1, 2, 3, 4, 5, 6, 7, 8, 9),  # <= 5
			week_predictor: None | RegressionResultsWrapper = None,
			tuneparams_1={
				'unfulfilled_demand_panelty': 1e3,
			},
			tuneparams_2={
				'turnon-transship_shipclass_restriction': 0, # making the algorithm slow
				'turnon-vessel_speed_optimization': 0,       # making the algorithm super slow
				'ctrparam-kts_buffer': 2,
				'ctrparam-transship_A': 100,
				'BigM-transship': 10000,
				'BigM-n_ships' : 2,  # at most 2 ships of the same type
				'BigM-saildays': 64,  # at most 9 weeks, hence less than 64 days
				'BigM-line_capacity': 30000  # at most 2 ships, with the largest capacity 14810
			}
		):
		"""To Do...
		"""
		trans_ports = portgraph.filtered_by_transship_capacity()
		od_pairs_dict = self.get_all_paths(portgraph, trans_ports)
		od_pairs = od_pairs_dict['od_pairs']
		od_pairs_paths = od_pairs_dict['od_pairs_path']
		# od_pairs_demand = od_pairs_dict['od_pairs_demand']
		unconnected = od_pairs_dict['unconnected']
		unconnected_demand = od_pairs_dict['unconnected_demand']

		# tune
		if len(unconnected) > 0:
			self.__total_cost = sum(unconnected_demand) * tuneparams_1['unfulfilled_demand_panelty']
		else:
			self.__total_cost = 0
		# TO DO:
		# divide the whole  `od_pairs` into several batches,
		# then solve the cargo allocation batch by batch
		if week_predictor is None:
			sol = self.fulfill_demands(
				od_pairs,
				od_pairs_paths,
				portgraph,
				vesselpool,
				week_levels,
				tuneparams_2)
			self.__total_cost += sol['total cost']
		else:
			sol = self.fulfill_demands_2(
				od_pairs,
				od_pairs_paths,
				portgraph,
				vesselpool,
				week_predictor)
			self.__total_cost += sol['total cost']

	def fulfill_demands(self,
			od_pairs: list[tuple[int, int]],
			od_pair_paths: list[list[Path]],
			portgraph: PortGraph,
			vesselpool: VesselPool,
			week_levels = (1/2, 1, 2, 3, 4, 5, 6, 7, 8, 9),  # <= 5
			tuneparams: dict[str, float] = {
				'turnon-transship_shipclass_restriction': 0, # making the algorithm slow
				'turnon-vessel_speed_optimization': 0,       # making the algorithm super slow
				'ctrparam-kts_buffer': 0,
				'ctrparam-transship_A': 100,
				'BigM-transship': 10000,
				'BigM-n_ships' : 2,  # at most 2 ships of the same type
				'BigM-saildays': 64,  # at most 9 weeks, hence less than 64 days
				'BigM-line_capacity': 30000  # at most 2 ships, with the largest capacity 14810
			}
		) -> dict:
		"""
		Optimization Problem:

		1. Key Decision Variables

		- Weekly Demand Flow: `X_{ OD_pair, path }`
		- Weekly Line Flow  : `Y_{ line, edge }`
		- Vessel Number     : `V_{ line, rank }`   - integer
		- Weeks             : `N_{ line, k }`    - binary

		2. Middle Expressions

		1) Weekly Transship Amounts: `Tr_{ line, port }`

		Sum of all `X_{od, p}` whose path `p` going through the port.
		Any element of `Tr` is in essense a linear combination of `X_{od, p}`.

		2) Line Capacity: `C_{ line }`

		Sum of all vessel's capacity in a line.
		Any element of `C` is in essense a linear combination of `Y_{T, seg}`.

		3. Model

		1) Weekly Transshipment Cost

		For each `line` and `port`, cost = K * duration, where

			K = transshipment cost per hour of the port,
			prods = productivities of the port for all vessel class, and
			duration (approximated) = Tr_{ line, port } / sum( prods ).

			prods @ (V_{ line, rank } >= 0)

		[[ Optional ]]
			Given the data, we know that not all vessels can be transshipped. Hence,
			we add a constraint by Big M's method:

			If Tr_{ line, port } > A, then there should be a vessel that is
			smaller than class `k`, where `A` is a tuning parameter, and
			`k = argmax prods_k` is the most suitable vessel class for transshipment
			in this port. More specifically,

				V_{ line, 0 } + V_{ line, 1 } + ... + V_{ line, k } >= z
				Tr_{ line, port } - A <= z * M

			Here, z = 1_{ Tr_{ line, port } > A }.

		2) Weekly Chartering Cost

		For each `line` and `vclass`, cost = 7 * K * V_{ line, vclass }, where
		`K` is daily chartering cost of the vessel class.

		3) Weekly Bukering Cost

		For each line, let's created a binary variable `KTS_{ line, k }` where
		the subscript `k` denotes for the level of speed. Then, we have a one-
		hot constraint:

			sum_{k} KTS_{ line, k } == 1

		and the weekly bukering cost is calculated by

			cost = sum_{r,k} V_{line, r} * KTS_{line, k} * daily_cost_rate_{r, k} * 7

		which is nonlinear although `KTS` is one-hot variable.

		Constraints: Speed * Sailing Days ~= Distance

		There are two options:
		For simplicity, we impose a constraint that

			daily_cost_rate_{r, k} == daily_cost_rate_{r, 15}
			KTS_{line, 5} == 1

		subject to constraint

			10 <= speed (distance / sailing days) <= 18

		[[ Optional ]]
			If you want to optimize the speed, we resort to Big M's method to linearlize
			this objective.

			Let W_{r,k} := V_{line, r} KTS_{line, k} and M = sup|V|. Then, adding
			these constraints:

				W_{r,k} <= M * KTS_{ line, k }
				W_{r,k} >= -M * KTS_{ line, k }
				W_{r,k} <= V_{line, r} + M * (1 - KTS_{ line, k })
				W_{r,k} >= V_{line, r} - M * (1 - KTS_{ line, k })

			In this case, the constraint is

				sum_{k} KTS_{line, k} * (k + 0.5) * 24 * sailing_days >= distance
				sum_{k} KTS_{line, k} * (k - 0.5) * 24 * sailing_days <= distance

			Note that this constraint is nonlinear: We have express the approximated
			time of staying in port for each line, which, denoted by `port_staying_days`,
			is a linear combination of demand flow `X_{ od, path }`. Hence,

				sailing_days = sum_{k} N_{line, k} * 7 - port_staying_days

			We can linearize the constraints using the same method:

			Let M = sup|sailing_days| and `W_{line, k} = sailing_days * KTS_{line, k}`.
			Then, the constraints are transformed to

				sum_{k} W_{line, k} * (k + 0.5) * 24 >= distance
				sum_{k} W_{line, k} * (k - 0.5) * 24 <= distance
				W_{line, k} <= M * KTS_{line, k}
				W_{line, k} >= -M * KTS_{line, k}
				W_{line, k} <= sailing_days + M * (1 - KTS_{line, k})
				W_{line, k} >= sailing_days - M * (1 - KTS_{line, k})

		4) Weekly Port-call Cost

		For each `port`...
		"""
		constraints = []
		obj_expr = 0.0

		n_lines = len(self.__lines_list)
		n_vessel_class = len(vesselpool.vessels_list)


		# region Key Variables
		#
		# (1) Create Weekly Demand Flow
		#     X_{od,p} = list[ X_{od} ] where X_{od} = list[ X_{od,p} ]
		demand_vars = []
		for od, paths_od in zip(od_pairs, od_pair_paths):
			demand_vars.append([])
			for idx_path, _ in enumerate(paths_od):
				demand_vars[-1].append(cp.Variable(name=f'X_{(int(od[0]), int(od[1]), idx_path)}', nonneg=True))

		# (2) Create Weekly Lines Flow
		#     Y_{ line, seg } = list[ Y_line ] where Y_line = list[ Y_{line, seg} ]
		flow_vars = []
		for line in self.__lines_list:
			flow_vars.append([])
			for slot in line.tolist_slot():
				flow_vars[-1].append(cp.Variable(name=f'y_({line.name(), slot.get_segment()})', nonneg=True))

		# (3) Create Number of Vessels for Each Line
		#     V_{ line, rank }
		ship_vars = cp.Variable(shape=(n_lines, n_vessel_class), name='V', integer=True)
		constraints.append(ship_vars >= 0)

		# (4) Create Number of Weeks for Each Line
		#     N_{ line, n }
		n_weeks = len(week_levels)
		week_vars = cp.Variable(shape=(n_lines, n_weeks), name='N', boolean=True)
		constraints.append(cp.sum(week_vars, axis=1)==1)
		#
		# endregion

		# region Middle Expressions
		def add_ele_to_counts_dict(dict_key: str, dict_val: int | cp.Expression, counts_dict: dict):
			if dict_key not in counts_dict:
				counts_dict[dict_key] = dict_val
			else:
				counts_dict[dict_key] += dict_val

		# Weekly Transshipment & Weekly Segment Demand Flow
		transshipments = np.array([
			[0 for _ in portgraph.tolist_port()]
				for _ in self.__lines_list], dtype=object)
		# >> `transship_amounts`: all demand of each port for each line
		#     - row     = lines
		#     - columns = ports
		seg_demand_flows: dict[str, cp.Expression] = {}
		# >> `seg_demand_flows`: all demand of each segment
		#     - key   = segment (od)
		#     - value = sum_{od} X_{od, p}
		for demand_vars_od, od, od_paths in zip(demand_vars, od_pairs, od_pair_paths):
			for idx_path, p in enumerate(od_paths):
				x_od_p = demand_vars_od[idx_path]
				# 1. there are loading/unloading at `o`, `d` ports
				first_line = p.get_first_service_line()
				last_line = p.get_last_service_line()
				first_idx_line = self.__lines_list.index(first_line)
				last_idx_line = self.__lines_list.index(last_line)
				transshipments[first_idx_line, od[0]] += x_od_p
				transshipments[last_idx_line, od[1]] += x_od_p
				service_line_old = None
				for slot in p.tolist_slot():
					slot_service = slot.get_service()
					if service_line_old is None:
						service_line_old = slot_service
					else:
						# 2. there is transshipment at port_1
						if slot.get_service() != service_line_old:
							old_service_idx = self.__lines_list.index(service_line_old)
							new_service_idx = self.__lines_list.index(slot_service)
							port_1 = slot.get_start()
							port_1_idx = portgraph.get_unique_index(port_1)
							transshipments[old_service_idx, port_1_idx] += x_od_p
							transshipments[new_service_idx, port_1_idx] += x_od_p
					# 3. add demand flow to segment
					seg = slot.get_segment()
					add_ele_to_counts_dict(str(seg), x_od_p, seg_demand_flows)

		# Weekly Segment Flow
		seg_flows: dict[str, cp.Expression] = {}
		# >> `seg_flows`: all flow of each segment
		#     - key   = segment (i, j)
		#     - value = sum_{i,j} Y_{p, i, j}
		for y_T, line in zip(flow_vars, self.__lines_list):
			for idx_line, slot in enumerate(line.tolist_slot()):
				seg = slot.get_segment()
				add_ele_to_counts_dict(str(seg), y_T[idx_line], seg_flows)

		# Path Distance `M_{ od, path }`
		all_paths_distance: list[list[float]] = []
		for od_paths in od_pair_paths:
			od_paths_distances: list[float] = []
			for path in od_paths:
				od_paths_distances.append(path.get_distance(portgraph))
			all_paths_distance.append(od_paths_distances)
		#
		# endregion

		# region Objective
		# 1. Weekly Chartering Cost
		daily_charter_costs = vesselpool.get_chartering_costs()
		obj_expr += 7 * cp.sum(ship_vars @ daily_charter_costs)

		# 2. Weekly Transshipment Cost
		# 1) transshipment cost per hour for each port
		ports_costs_transsip = [port.cost_transship for port in portgraph.tolist_port()]
		# 2) hour productivity of each port
		ports_prods = [port.get_producticity(vesselpool) for port in portgraph.tolist_port()]
		ports_gross_prod = [sum(prods) for prods in ports_prods]
		# 3) suitable type of vessel for each port
		ports_suitable_v = [np.argmax(prods) for prods in ports_prods]
		# 4) Port staying days per week for each line (row) and each port (rolumn)
		matrix_stay_days = np.array([[0 for _ in portgraph.tolist_port()]for _ in self.__lines_list], dtype=object)

		for idx_line in range(n_lines):
			matrix_stay_days[idx_line, :] = transshipments[idx_line, :] / ports_gross_prod / 24
			obj_expr += matrix_stay_days[idx_line, :] @ ports_costs_transsip

			# Big M's method
			for idx_port in range(portgraph.get_number_of_ports()):
				if tuneparams['turnon-transship_shipclass_restriction'] > 0.5:
					transamount = transshipments[idx_line, idx_port]
					z = cp.Variable(boolean=True)
					constraints.append(transamount - tuneparams['ctrparam-transship_A'] <= z * tuneparams['BigM-transship'])
					idf = ports_suitable_v[idx_port]
					constraints.append(cp.sum(ship_vars[idx_line, : (idf + 1)]) >= z)

		# 3. Weekly Bukering Cost
		daily_bukering_cost_rates, speed_level0 = vesselpool.get_bukering_costs()  # shape = (rank, speed)
		n_speed_level = daily_bukering_cost_rates.shape[1]
		KTS_levels = np.arange(speed_level0, speed_level0 + n_speed_level)
		list_saildays = []

		for idx_line, line in enumerate(self.__lines_list):
			line_ship_vars = ship_vars[idx_line, :]   # shape = (rank,)
			line_distance = line.get_distance(portgraph)
			line_port_stay_days = np.sum(matrix_stay_days[idx_line, :])
			line_sailing_days = 7 * (week_vars[idx_line, :] @ week_levels) - line_port_stay_days
			list_saildays.append(line_sailing_days)
			buf = tuneparams['ctrparam-kts_buffer']

			if tuneparams['turnon-vessel_speed_optimization'] < 1/2:
				obj_expr += 7 * line_ship_vars @ vesselpool.get_bukering_cost_middle()
				# Constraint: KTS_min <= Speed (distance / sailing days) <= KTS_max
				constraints.append(line_sailing_days >= 0.5 * 7)
				constraints.append(line_distance >= 24 * line_sailing_days * (KTS_levels[0] - buf))
				constraints.append(line_distance <= 24 * line_sailing_days * (KTS_levels[-1] + buf))

			else:  # if we want to further optimize the bukering cost by determine optimal speed
				# Auxiliary Variable:
				#     W_{r,k} = line_ship_vars_{r} * KTS_vars_{k}
				aux_W_shipspeed = cp.Variable(shape=daily_bukering_cost_rates.shape)  # shape = (rank, speed)
				obj_expr += 7 * cp.multiply(aux_W_shipspeed, daily_bukering_cost_rates).sum()

				# Binary variable for speed
				#     KTS_vars_{k}
				line_KTS_vars = cp.Variable(name='Z', shape=(n_speed_level), boolean=True)  # shape = (speed,)
				constraints.append(cp.sum(line_KTS_vars) == 1)

				KTS_line_stack = cp.vstack([line_KTS_vars] * n_vessel_class)
				line_ship_stack = cp.vstack([line_ship_vars] * n_speed_level).T
				big_M_nship = tuneparams['BigM-n_ships']
				bigM_saildays = tuneparams['BigM-saildays']
				constraints.append(aux_W_shipspeed <= big_M_nship * KTS_line_stack)
				constraints.append(aux_W_shipspeed >= -big_M_nship * KTS_line_stack)
				constraints.append(aux_W_shipspeed <= line_ship_stack + big_M_nship * (1 - KTS_line_stack))
				constraints.append(aux_W_shipspeed >= line_ship_stack - big_M_nship * (1 - KTS_line_stack))

				# Constraint: Optimal Speed * Sailing Days ~= Distance
				aux_W_speedsaildays = cp.Variable(shape=n_speed_level)
				constraints.append(24 * aux_W_speedsaildays @ (KTS_levels + 1) >= line_distance)
				constraints.append(24 * aux_W_speedsaildays @ (KTS_levels - 1) <= line_distance)

				for idx_kts in range(n_speed_level):
					z_kts = line_KTS_vars[idx_kts]
					constraints.append(aux_W_speedsaildays[idx_kts] <= bigM_saildays * z_kts)
					constraints.append(aux_W_speedsaildays[idx_kts] >= -bigM_saildays * z_kts)
					constraints.append(aux_W_speedsaildays[idx_kts] <= line_sailing_days + bigM_saildays * (1 - z_kts))
					constraints.append(aux_W_speedsaildays[idx_kts] >= line_sailing_days - bigM_saildays * (1 - z_kts))

		# 4. Weekly Port Call Cost
		# for port in line.tolist_port():
		# 	portcall_cost_rate = port.get_port_call_costs(vesselpool)
		# 	for idx_V, V in enumerate(ships_of_serviceline):
		# 		obj_expr += V * portcall_cost_rate[idx_V] / weeks[idx_line]
		#
		# endregion

		# region Key Constraints
		# Constraint: (Weekly Demand Flow) sum X_{odp} >= (Weekly Demand) D_{od}
		for pair_od, demand_vars_od in zip(od_pairs, demand_vars):
			demand_od = portgraph.get_demand_by_idx(pair_od[0], pair_od[1])
			demand_od_fulfill = 0
			for x_od_p in demand_vars_od:
				demand_od_fulfill += x_od_p
			constraints.append(demand_od_fulfill >= demand_od)

		# Constraint: (Weekly Edge Flow) sum_T Y_{T, i, j} >= (Weekly Line Demand Flow) sum_{p has (i,j)} X_{o, d, p}
		for seg_id, seg_demand_flow in seg_demand_flows.items():
			constraints.append(seg_flows[seg_id] >= seg_demand_flow)

		# Constraint: (Weekly Line Flow) Y <= (Weekly Line Capacity) C
		ships_capacities = [s.vessel_capacity for s in vesselpool.vessels_list]
		line_capacities = ship_vars @ ships_capacities  # shape = (line,)
		bigM_line_capacity = tuneparams['BigM-line_capacity']

		for idx_line in range(n_lines):
			line_capacity = line_capacities[idx_line]
			line_week_vars = week_vars[idx_line, :]
			aux_capacity_weeks = cp.Variable(shape=n_weeks)  # Z_{week=k} * LC / k for each k
			constraints.extend(Y_T_seg <= cp.sum(aux_capacity_weeks) for Y_T_seg in flow_vars[idx_line])
			for idx_wk, wk in enumerate(week_levels):  # loop over weeks
				aux_C_Wk = aux_capacity_weeks[idx_wk]
				is_wk = line_week_vars[idx_wk]
				constraints.append(aux_C_Wk <= bigM_line_capacity * is_wk)
				constraints.append(aux_C_Wk >= -bigM_line_capacity * is_wk)
				constraints.append(aux_C_Wk <= line_capacity / wk + bigM_line_capacity * (1 - is_wk))
				constraints.append(aux_C_Wk >= line_capacity / wk - bigM_line_capacity * (1 - is_wk))
		#
		# endregion

		# region Call Solver
		prob = cp.Problem(cp.Minimize(obj_expr), constraints)
		prob.solve(solver=cp.SCIP, verbose=False)
		# prob.solve(solver=cp.ECOS)
		# prob.solve(solver=cp.GLPK_MI)  # much slower than SCIP
		#
		#endregion

		return {
			'total cost': typing.cast(float, prob.value),
			'demand rounts': demand_vars,
			'line flows': flow_vars,
			'weeks': week_vars,
			'ships': ship_vars,
			'port staying days': matrix_stay_days,
			'line sailing days': list_saildays,
		}

	def fulfill_demands_2(self,
			od_pairs: list[tuple[int, int]],
			od_pair_paths: list[list[Path]],
			portgraph: PortGraph,
			vesselpool: VesselPool,
			model: RegressionResultsWrapper
		):
		"""This is a simplified version of the subroutine `fulfill_demands`

		In this routine, `weeks` of each line is priorly estimated
		"""
		constraints = []
		obj_expr = 0.0

		n_lines = len(self.__lines_list)
		n_vessel_class = len(vesselpool.vessels_list)

		# predict weeks
		week_vars = apply_prediction(model, self.__lines_list, portgraph)

		# region Key Variables
		#
		# (1) Create Weekly Demand Flow
		#     X_{od,p} = list[ X_{od} ] where X_{od} = list[ X_{od,p} ]
		demand_vars = []
		for od, paths_od in zip(od_pairs, od_pair_paths):
			demand_vars.append([])
			for idx_path, _ in enumerate(paths_od):
				demand_vars[-1].append(cp.Variable(name=f'X_{(int(od[0]), int(od[1]), idx_path)}', nonneg=True))

		# (2) Create Weekly Lines Flow
		#     Y_{ line, seg } = list[ Y_line ] where Y_line = list[ Y_{line, seg} ]
		flow_vars = []
		for line in self.__lines_list:
			flow_vars.append([])
			for slot in line.tolist_slot():
				flow_vars[-1].append(cp.Variable(name=f'y_({line.name(), slot.get_segment()})', nonneg=True))

		# (3) Create Number of Vessels for Each Line
		#     V_{ line, rank }
		ship_vars = cp.Variable(shape=(n_lines, n_vessel_class), name='V', integer=True)
		constraints.append(ship_vars >= 0)
		#
		# endregion

		# region Middle Expressions
		def add_ele_to_counts_dict(dict_key: str, dict_val: int | cp.Expression, counts_dict: dict):
			if dict_key not in counts_dict:
				counts_dict[dict_key] = dict_val
			else:
				counts_dict[dict_key] += dict_val

		# Weekly Transshipment & Weekly Segment Demand Flow
		transshipments = np.array([
			[0 for _ in portgraph.tolist_port()]
				for _ in self.__lines_list], dtype=object)
		# >> `transship_amounts`: all demand of each port for each line
		#     - row     = lines
		#     - columns = ports
		seg_demand_flows: dict[str, cp.Expression] = {}
		# >> `seg_demand_flows`: all demand of each segment
		#     - key   = segment (od)
		#     - value = sum_{od} X_{od, p}
		for demand_vars_od, od, od_paths in zip(demand_vars, od_pairs, od_pair_paths):
			for idx_path, p in enumerate(od_paths):
				x_od_p = demand_vars_od[idx_path]
				# 1. there are loading/unloading at `o`, `d` ports
				first_line = p.get_first_service_line()
				last_line = p.get_last_service_line()
				first_idx_line = self.__lines_list.index(first_line)
				last_idx_line = self.__lines_list.index(last_line)
				transshipments[first_idx_line, od[0]] += x_od_p
				transshipments[last_idx_line, od[1]] += x_od_p
				service_line_old = None
				for slot in p.tolist_slot():
					slot_service = slot.get_service()
					if service_line_old is None:
						service_line_old = slot_service
					else:
						# 2. there is transshipment at port_1
						if slot.get_service() != service_line_old:
							old_service_idx = self.__lines_list.index(service_line_old)
							new_service_idx = self.__lines_list.index(slot_service)
							port_1 = slot.get_start()
							port_1_idx = portgraph.get_unique_index(port_1)
							transshipments[old_service_idx, port_1_idx] += x_od_p
							transshipments[new_service_idx, port_1_idx] += x_od_p
					# 3. add demand flow to segment
					seg = slot.get_segment()
					add_ele_to_counts_dict(str(seg), x_od_p, seg_demand_flows)

		# Weekly Segment Flow
		seg_flows: dict[str, cp.Expression] = {}
		# >> `seg_flows`: all flow of each segment
		#     - key   = segment (i, j)
		#     - value = sum_{i,j} Y_{p, i, j}
		for y_T, line in zip(flow_vars, self.__lines_list):
			for idx_line, slot in enumerate(line.tolist_slot()):
				seg = slot.get_segment()
				add_ele_to_counts_dict(str(seg), y_T[idx_line], seg_flows)

		# Path Distance `M_{ od, path }`
		all_paths_distance: list[list[float]] = []
		for od_paths in od_pair_paths:
			od_paths_distances: list[float] = []
			for path in od_paths:
				od_paths_distances.append(path.get_distance(portgraph))
			all_paths_distance.append(od_paths_distances)
		#
		# endregion

		# region Objective
		# 1. Weekly Chartering Cost
		daily_charter_costs = vesselpool.get_chartering_costs()
		obj_expr += 7 * cp.sum(ship_vars @ daily_charter_costs)

		# 2. Weekly Transshipment Cost
		# 1) transshipment cost per hour for each port
		ports_costs_transsip = [port.cost_transship for port in portgraph.tolist_port()]
		# 2) hour productivity of each port
		ports_prods = [port.get_producticity(vesselpool) for port in portgraph.tolist_port()]
		ports_gross_prod = [sum(prods) for prods in ports_prods]
		# 3) Port staying days per week for each line (row) and each port (rolumn)
		matrix_stay_days = np.array([[0 for _ in portgraph.tolist_port()]for _ in self.__lines_list], dtype=object)

		for idx_line in range(n_lines):
			matrix_stay_days[idx_line, :] = transshipments[idx_line, :] / ports_gross_prod / 24
			obj_expr += matrix_stay_days[idx_line, :] @ ports_costs_transsip

		# 3. Weekly Bunkering Cost
		daily_bunkering_cost_rates, speed_level0 = vesselpool.get_bukering_costs()  # shape = (rank, speed)
		n_speed_level = daily_bunkering_cost_rates.shape[1]
		KTS_levels = np.arange(speed_level0, speed_level0 + n_speed_level)
		list_saildays = []

		for idx_line, line in enumerate(self.__lines_list):
			line_ship_vars = ship_vars[idx_line, :]   # shape = (rank,)
			line_port_stay_days = np.sum(matrix_stay_days[idx_line, :])
			line_sailing_days = 7 * week_vars[idx_line] - line_port_stay_days
			list_saildays.append(line_sailing_days)
			obj_expr += 7 * line_ship_vars @ vesselpool.get_bukering_cost_middle()

		# 4. Weekly Port Call Cost
		# for port in line.tolist_port():
		# 	portcall_cost_rate = port.get_port_call_costs(vesselpool)
		# 	for idx_V, V in enumerate(ships_of_serviceline):
		# 		obj_expr += V * portcall_cost_rate[idx_V] / weeks[idx_line]
		#
		# endregion

		# region Key Constraints
		# Constraint: (Weekly Demand Flow) sum X_{odp} >= (Weekly Demand) D_{od}
		for pair_od, demand_vars_od in zip(od_pairs, demand_vars):
			demand_od = portgraph.get_demand_by_idx(pair_od[0], pair_od[1])
			demand_od_fulfill = 0
			for x_od_p in demand_vars_od:
				demand_od_fulfill += x_od_p
			constraints.append(demand_od_fulfill >= demand_od)

		# Constraint: (Weekly Edge Flow) sum_T Y_{T, i, j} >= (Weekly Line Demand Flow) sum_{p has (i,j)} X_{o, d, p}
		for seg_id, seg_demand_flow in seg_demand_flows.items():
			constraints.append(seg_flows[seg_id] >= seg_demand_flow)

		# Constraint: (Weekly Line Flow) Y <= (Weekly Line Capacity) C
		ships_capacities = [s.vessel_capacity for s in vesselpool.vessels_list]
		line_capacities = ship_vars @ ships_capacities  # shape = (line,)

		for idx_line in range(n_lines):
			line_capacity = line_capacities[idx_line]
			weekly_line_capacity = line_capacity / week_vars[idx_line]
			constraints.extend(Y_T_seg <= weekly_line_capacity for Y_T_seg in flow_vars[idx_line])
		#
		# endregion

		# region Call Solver
		prob = cp.Problem(cp.Minimize(obj_expr), constraints)
		prob.solve(solver=cp.SCIP, verbose=False)
		# prob.solve(solver=cp.ECOS)
		# prob.solve(solver=cp.GLPK_MI)  # much slower than SCIP
		#
		#endregion

		return {
			'total cost': typing.cast(float, prob.value),
			'line flows': flow_vars,
			'weeks': week_vars,
			'demand rounts': demand_vars,
			'ships': ship_vars,
			'port staying days': matrix_stay_days,
			'line sailing days': list_saildays,
		}

	def solve_plan(self) -> None:
		"""
		Consider the following:
			1. Daily port call limit
			2. Storage Cost
		"""
		pass
#
# endregion
