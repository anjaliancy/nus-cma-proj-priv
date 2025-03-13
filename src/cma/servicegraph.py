"""
Module `servicegraph`

Define all service graph related classes and methods
"""

# from __future__ import annotations  # For Python < 3.11
import typing
import time
import math
import cvxpy as cp
import numpy as np

from .vessel import Vessel, VesselPool
from .port import Port, PortGraph
from .serviceline import ServiceLine, LineAction, Path, Slot, Segment

from .rl_utils import MatrixAnalyzer


class GraphAction:
	"""This class defines the class of action that adjust the graph of servicelines

	The action looks like: ('line ID', 'add'/'delete', locs)
	"""
	line: int
	cmd: str
	loc: list[int]

	def __init__(self, line: int, cmd: str, loc: list[int]):
		self.line = line
		self.cmd = cmd
		self.loc = loc

	def __repr__(self) -> str:
		return str([self.line, self.cmd, self.loc])

	def get_line_action(self, serviceline: ServiceLine, portgraph: PortGraph) -> LineAction:
		return LineAction(self.cmd, self.loc)

	def __eq__(self, other) -> bool:
		if self.line != other.line:
			return False
		if self.cmd != other.cmd:
			return False
		if self.loc != other.loc:
			return False
		return True

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

################################################################################
# Basic Attributes & Operations
################################################################################

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

	def get_adjacency_matrices(self, portgraph: PortGraph) -> list[np.matrix]:
		returned_adjs = []
		for line in self.__lines_list:
			returned_adjs.append(line.get_adjacency_matrix(portgraph))
		return returned_adjs


################################################################################
# Action related
################################################################################

	def update_by_graph_action(self, graph_action: GraphAction, portgraph: PortGraph) -> 'ServiceGraph':
		old_line = self.__lines_list[graph_action.line]
		line_action = graph_action.get_line_action(old_line, portgraph)
		new_line = old_line.apply_action(line_action, portgraph)

		new_services: list[ServiceLine] = self.__lines_list.copy()
		new_services[graph_action.line] = new_line
		new_graph = ServiceGraph(new_services)
		return new_graph

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


################################################################################
# Path related
################################################################################

	def get_all_lines_contains(self, ports: list[Port]) -> list[ServiceLine]:
		re = set()
		for line in self.__lines_list:
			for port in ports:
				if line.has_port(port):
					re.add(line)
		return list(re)

	def get_paths(self, start: Port, end: Port, trans_ports) -> list[Path]:
		"""Find out all paths the connects an OD pair
		"""
		paths_list: list[Path] = []
		lines_has_o: list[ServiceLine] = self.get_all_lines_contains([start])
		lines_has_d: list[ServiceLine] = self.get_all_lines_contains([end])
		for line_o in lines_has_o:
			for line_d in lines_has_d:
				# case 1:
				if line_o == line_d:
					paths_list.append(line_o.get_shortest_path(start, end))
					continue
				# case 2:
				hubs = list(set(line_o.tolist_port()) & set(line_d.tolist_port()))
				if len(hubs) == 0:
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

	def get_all_paths(self, portgraph: PortGraph,
		trans_port_draft_req=0, trans_cost_req=75) \
		-> tuple[
			list[tuple[int, int]], list[list[Path]], list[tuple[int]]
		]:
		"""Searching all connected paths among all ports in the network

		input:
			`trans_port_draft_req`: required draft for transshipment

		return:
			`od_pairs`: list of port-index pairs (ports are 0 indexed)
			`paths`
			`unconnected`
		"""
		trans_ports_1 = portgraph.filter_by_max_draft(trans_port_draft_req)
		trans_ports_2 = portgraph.filtered_by_transship_cost(trans_cost_req)
		trans_ports = list(set(trans_ports_1) & set(trans_ports_2))
		od_pairs: list[tuple[int, int]] = portgraph.get_all_od_pairs()
		paths: list[list[Path]] = []
		connected = []
		unconnected = []

		for pair in od_pairs:
			port_o = portgraph.get_port_by_idx(pair[0])
			port_d = portgraph.get_port_by_idx(pair[1])
			paths_od = self.get_paths(port_o, port_d, trans_ports)
			if len(paths_od) > 0:
				paths.append(paths_od)
				connected.append(pair)
			else:
				unconnected.append(pair)
		return connected, paths, unconnected


################################################################################
# Key method: solve the minimum cost
################################################################################

	def solve_approximated_cost(self, portgraph: PortGraph, vesselpool: VesselPool,
			display: bool = False, trans_port_draft_req=0, trans_cost_req=75) -> dict:
		"""
		return:
			capacities, demand_vars, flow_vars
		"""
		def create_demand_vars(od_pairs, paths) -> list[list[cp.Variable]]:
			"""Create:
				X_{o,d,p} = list[ X_{o,d} ] where X_{o,d} = list[ X_{o,d,p} ]
			"""
			demand_vars = []
			for od, p_od in zip(od_pairs, paths):
				x_od = []
				for p_idx, p in enumerate(p_od):
					x_odp_label = f'X_{(int(od[0]), int(od[1]), p_idx)}'
					x_odp = cp.Variable(name=x_odp_label)
					x_od.append(x_odp)
				demand_vars.append(x_od)
			return demand_vars

		def create_flow_vars() -> list[list[cp.Variable]]:
			"""Create
				Y_{T, seg} = list[ Y_T ] where Y_T = list[ Y_{T, seg} ]
			"""
			flow_vars = []
			for line in self.__lines_list:
				y_Ts = []
				for slot in line.tolist_slot():
					y_T_seg_name = f'y_({line.name(), slot.get_segment()})'
					y_Ts.append(cp.Variable(name=y_T_seg_name))
				flow_vars.append(y_Ts)
			return flow_vars

		def create_capacities() -> tuple[list[list[cp.Variable]], list[cp.Expression]]:
			"""Create
				V_{T,s} is a matrix of (lines, 13)
				C_{T} is a vector of lines
			"""
			ships: list[list[cp.Variable]] = []
			capacities = []
			for line in self.__lines_list:
				ships_line = []
				line_capacity = 0
				for ship in vesselpool.vessels_list:
					ship_var = cp.Variable(name=f'V_({line.name(), ship.vessel_rank})')
					ships_line.append(ship_var)
					line_capacity += ship.vessel_capacity * ship_var
				capacities.append(line_capacity)
				ships.append(ships_line)
			return ships, capacities

		# def create_inv_speed() -> cp.Variable:
		# 	"""Create
		# 		inv_V = 1/v, a vector of service T
		# 	"""
		# 	number_of_lines = len(self.__lines_list)
		# 	inv_V = cp.Variable(shape=number_of_lines, name='inv_V')
		# 	return inv_V

		# def create_weeks() -> cp.Variable:
		# 	"""Create
		# 		N is a vector of service T
		# 	"""
		# 	number_of_lines = len(self.__lines_list)
		# 	weeks = cp.Variable(shape=number_of_lines, name='N')
		# 	return weeks

		start_time = time.time()

		# Find all paths
		#
		od_pairs, all_paths, _ \
			= self.get_all_paths(portgraph, trans_port_draft_req, trans_cost_req)
		if display:
			print(f'get all path P finished: {round(time.time() - start_time, 2)}s')
			start_time = time.time()

		# Create Decision Variables
		#
		demand_vars = create_demand_vars(od_pairs, all_paths)
		if display:
			print(f'create all demand vars X finished: {round(time.time() - start_time, 2)}s')
			start_time = time.time()
		flow_vars = create_flow_vars()
		if display:
			print(f'create all flow vars Y finished: {round(time.time() - start_time, 2)}s')
			start_time = time.time()
		ship_vars, capacities = create_capacities()
		if display:
			print(f'create all capacities vars C, V finished: {round(time.time() - start_time, 2)}s')
			start_time = time.time()
		# weeks = create_weeks()
		# if display:
		# 	print(f'create weeks n_T finished: {round(time.time() - start_time, 2)}s')
		# 	start_time = time.time()
		# inverse_Speed = create_inv_speed()
		# if display:
		# 	print(f'create inverse speed inv_V_T finished: {round(time.time() - start_time, 2)}s')
		# 	start_time = time.time()

		# Statistics
		#
		def add_ele_to_counts_dict(dict_key, dict_val, counts_dict: dict):
			if dict_key not in counts_dict:
				counts_dict[dict_key] = dict_val
			else:
				counts_dict[dict_key] += dict_val
		seg_demand_flows = {}
		#
		# a matrix with rows representing for lines and columns for ports
		transship_statistics = np.array([
			[0 for _ in portgraph.tolist_port()]
				for _ in self.__lines_list], dtype=object)

		for x_od, od, od_paths in zip(demand_vars, od_pairs, all_paths):
			for p_idx, p in enumerate(od_paths):
				x_odp = x_od[p_idx]

				# 1. deal with the (o, d) ports
				first_line = p.get_first_service_line()
				last_line = p.get_last_service_line()
				first_line_idx = self.__lines_list.index(first_line)
				last_line_idx = self.__lines_list.index(last_line)
				transship_statistics[first_line_idx, od[0]] += x_odp
				transship_statistics[last_line_idx, od[1]] += x_odp

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
							transship_statistics[old_service_idx, port_1_idx] += x_odp
							transship_statistics[new_service_idx, port_1_idx] += x_odp
					# 3. add demand flow to segment
					seg = slot.get_segment()
					add_ele_to_counts_dict(str(seg), x_odp, seg_demand_flows)

		if display:
			print(f'Statistics finished: {round(time.time() - start_time, 2)}s')
			start_time = time.time()

		# Create Constraints
		constraints = []

		# Constraint: Non-negativity
		#
		for x_od in demand_vars:
			for x_odp in x_od:
				constraints.append(x_odp >= 0)
		for y_T in flow_vars:
			for y_T_seg in y_T:
				constraints.append(y_T_seg >= 0)
		for ships_line in ship_vars:
			for ship in ships_line:
				constraints.append(ship >= 0)
		# constraints.append(weeks >= 0)
		# constraints.append(inverse_Speed >= 0)
		if display:
			print(f'Constraints `Non-negativity` Created: {round(time.time() - start_time, 2)}s')
			print(f'Constraints number = {len(constraints)}')
			start_time = time.time()

		# Constraint: Line Flow Y <= Line Capacity C
		#
		number_of_lines = len(self.__lines_list)
		for line_idx in range(number_of_lines):
			line_capacity = capacities[line_idx]
			Y_Ts = flow_vars[line_idx]
			constraints += [Y_T_seg <= line_capacity for Y_T_seg in Y_Ts]
		if display:
			print(f'Constraints `Y <= Line Capacity C` Created: {round(time.time() - start_time, 2)}s')
			print(f'Constraints number = {len(constraints)}')
			start_time = time.time()

		# Constraint: Slot Flow sum_T Y_{T, i, j} >= Slot Demand Flow sum_{p has (i,j)} X_{o, d, p}
		#
		# 1. statistics of segment flows
		seg_flow = {}
		for y_T, line in zip(flow_vars, self.__lines_list):
			for idx, slot in enumerate(line.tolist_slot()):
				seg = slot.get_segment()
				add_ele_to_counts_dict(str(seg), y_T[idx], seg_flow)
		# 2. add constraint
		for seg_id, sum_flow in seg_flow.items():
			constraints.append(sum_flow >= seg_demand_flows[seg_id])
		if display:
			print(f'Constraints sum Y_(T,i,j) >= sum X_(o,d,p) Created: {round(time.time() - start_time, 2)}s')
			print(f'Constraints number = {len(constraints)}')
			start_time = time.time()

		# Constraint: sum X_{odp} >= D_{od}
		#
		for pair_od, x_od in zip(od_pairs, demand_vars):
			demand_od = portgraph.get_demand_by_idx(pair_od[0], pair_od[1])
			demand_od_fulfill = 0
			for x_odp in x_od:
				demand_od_fulfill += x_odp
			constraints.append(demand_od_fulfill >= demand_od)
		if display:
			print(f'Constraints sum X_(odp) >= D_(od) Created: {round(time.time() - start_time, 2)}s')
			print(f'Constraints number = {len(constraints)}')
			start_time = time.time()

		# Constraint: Max Daily Port Call Limits
		#
		# 1. statistics of port calls
		port_call_counts = {}
		for line_idx, line in enumerate(self.__lines_list):
			line_ship_number = 0
			line_ships = ship_vars[line_idx]
			for ship in line_ships:
				line_ship_number += ship
			for port in line.tolist_port():
				add_ele_to_counts_dict(port.get_id(), line_ship_number, port_call_counts)
		# 2. add constraints
		for port_id, number_of_calls in port_call_counts.items():
			port = portgraph.get_port(port_id)
			constraints.append(number_of_calls <= port.max_daily_call)
		if display:
			print(f'Constraints Max Daily Port Call Limits Created: {round(time.time() - start_time, 2)}s')
			print(f'Constraints number = {len(constraints)}')
			start_time = time.time()

		# Define OBJ
		#
		obj_expr = 0.0
		#
		# 0. Prepare: create path distances M_{o, d, p}
		# all_paths_distance: list[list[float]] = []
		# for od_paths in all_paths:
		# 	od_paths_distances: list[float] = []
		# 	for path in od_paths:
		# 		od_paths_distances.append(path.get_distance(portgraph))
		# 	all_paths_distance.append(od_paths_distances)
		# if display:
		# 	print(f'get all path distances M finished: {round(time.time() - start_time, 2)}s')
		# 	start_time = time.time()
		#
		# 1. chartering cost and port call cost
		# for idx, line in enumerate(self.__lines_list):
		# 	ships_of_serviceline = ships[idx, :]
		# 	# (1) chartering cost
		# 	obj_expr += ships_of_serviceline @ vesselpool.get_chartering_costs() * 7
		# 	# (2) port call cost
		# 	for port in line.tolist_port():
		# 		obj_expr += ships_of_serviceline @ port.get_port_call_costs(vesselpool)
		# 2. transshipment cost & bukering cost
		bukering_unit_cost = vesselpool.get_bukering_cost_middle()
		bukering_cost = 0
		transship_cost = 0
		for line_idx, line in enumerate(self.__lines_list):
			line_distance = line.get_distance(portgraph)
			line_ships = ship_vars[line_idx]
			for ship, unit_cost in zip(line_ships, bukering_unit_cost):
				bukering_cost += line_distance * ship * unit_cost
		obj_expr += bukering_cost

		for port_idx, port in enumerate(portgraph.tolist_port()):
			port_prods = port.get_producticity_for_each_vessel_type(vesselpool)
			port_gross_prod = np.sum(port_prods)
			transship_amount = np.sum(transship_statistics[:, port_idx])
			duration = transship_amount / port_gross_prod
			transship_cost += duration * port.cost_transship
		obj_expr += transship_cost

		if display:
			print(f'Objective Created: {round(time.time() - start_time, 2)}s')
			print(obj_expr)
			start_time = time.time()

		# problem
		prob = cp.Problem(cp.Minimize(obj_expr), constraints)
		# solve
		prob.solve(solver=cp.GLPK, verbose=True)

		self.__total_cost = typing.cast(float, prob.value)
		if display:
			print(f'Problem solved: {round(time.time() - start_time, 2)}s')
		return {
			'line flows': flow_vars,
			'demand rounts': demand_vars,
			# 'weeks': weeks,
			'ships': ship_vars,
		}

	def solve_plan(self) -> None:
		pass
