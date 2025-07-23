"""
port.py

Define all port related classes and methods
"""
from typing import Tuple, Literal
from importlib import resources
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from matplotlib.lines import Line2D
from shapely.geometry import Point
from shapely.ops import transform

import geopandas as gpd
import numpy as np
import pandas as pd

from .vessel import VesselPool

class Port:
	"""class Port

	The bundle of all information about a port
		- ID
		- Name
		- Location (longitude, latitude)
		- Port call cost rate
		- Transshipment cost rate
	"""
	__id: str
	__name: str
	__longitude: float
	__latitude: float

	fit_vessel_ranks: dict[int, int]  # this is not an explicit constraint but more a data limitation constraint
	berth_productivity: dict[int, float]
	cost_portcall: dict[int, float]
	cost_transship: float
	cost_storage: float
	transshipment_capacity: bool
	max_draft: float
	max_daily_call: int
	max_line_visit: int

	def __init__(self, port_id: str, name: str, longitude: float, latitude: float,
			fit_vessel_ranks: dict[int, int],      # vessel rank : number
			berth_productivity: dict[int, float],  # vessel rank : productivity
			cost_portcall: dict[int, float],       # vessel rank : average cost
			cost_transship: float,                 #
			cost_storage: float,                   #
			transshipment_capacity: bool,          #
			max_draft: float,                      #
			max_daily_call: int,                   #
			max_line_visit: int=2                  # max number of visits for each line
	):
		self.__id = port_id
		self.__name = name
		self.__longitude = longitude
		self.__latitude = latitude
		self.max_line_visit = max_line_visit
		self.max_draft = max_draft
		self.max_daily_call = max_daily_call
		self.fit_vessel_ranks = fit_vessel_ranks
		self.berth_productivity = berth_productivity
		self.cost_portcall = cost_portcall
		self.cost_transship = cost_transship
		self.cost_storage = cost_storage
		self.transshipment_capacity = transshipment_capacity

	def __repr__(self) -> str:
		return self.__id

	def get_id(self) -> str:
		return self.__id

	def get_name(self) -> str:
		return self.__name

	def get_location(self) -> tuple[float, float]:
		return self.__longitude, self.__latitude

	def get_max_number_of_visit(self) -> int:
		return self.max_line_visit

	def get_producticity(self, vesselpool: VesselPool) -> list[float]:
		"""
		Input: all vessels

		Productivity for each vessel type
		"""
		n_vessel_ranks = vesselpool.get_number_of_types()
		productivities = [0.0 for _ in range(n_vessel_ranks)]
		for vclass, prod in self.berth_productivity.items():
			if vclass <= n_vessel_ranks:
				productivities[vclass - 1] = prod
		return productivities

	def get_portcall_costs(self, vesselpool: VesselPool) -> list[float]:
		"""
		Input: all vessels

		Return: a list of port call cost of each vessel

		Note: `infty` for unavailable ship types
		"""
		n_vessel_ranks = vesselpool.get_number_of_types()
		portcall_costs = [2e4 for _ in range(n_vessel_ranks)]
		for vclass, portcall_cost in self.cost_portcall.items():
			if vclass <= n_vessel_ranks:
				portcall_costs[vclass - 1] = portcall_cost
		return portcall_costs

	def check_is_vessel_fit(self, v_rank: int) -> bool:
		return v_rank in self.fit_vessel_ranks

class PortPool:
	"""class PortPool

	The pool of all available ports. This class is in essense a list of
	ports, where you can manage these ports easily.
	"""
	__port_list: list[Port]

	def __init__(self, port_list: list[Port] = []):
		self.__port_list = port_list

	def __repr__(self) -> str:
		return str(self.__port_list)

	def update(self, port_list: list[Port]):
		self.__port_list = port_list

	def tolist_port(self) -> list[Port]:
		return self.__port_list

	def get_number_of_ports(self) -> int:
		return len(self.__port_list)

	def plot(self, selected_countries: list[str],
			plot_port_id: bool=False, display_info=True, center_pacific=False
		) -> Tuple[Figure, Axes, 'PortPool']:
		"""
		This function input `selected_asia_countries` as a filter and
		return a filtered new collection of ports that is only contained
		in the graph.
		"""
		def shift_longitude(geom):
			def shift_coords(x, y, z=None):
				x_new = x + 360 if x < 0 else x
				return (x_new, y) if z is None else (x_new, y, z)
			return transform(shift_coords, geom)

		MAP_FILE_PATH = '110m_cultural/ne_110m_admin_0_countries.shp'
		file = resources.files("cma.res").joinpath(MAP_FILE_PATH)
		geometry = [Point(port.get_location()) for port in self.__port_list]
		gdf_port = gpd.GeoDataFrame({
			'Port': [port.get_id() for port in self.__port_list],
			'geometry': geometry
			})
		world = gpd.read_file(str(file))
		if not isinstance(world, gpd.GeoDataFrame):
			raise ValueError('Invalid file', file)
		world_names = world['NAME']
		if not isinstance(world_names, pd.Series):
			raise ValueError('Invalid file', file)

		if center_pacific:
			world["geometry"] = world["geometry"].apply(shift_longitude)
			gdf_port['geometry'] = gdf_port['geometry'].apply(shift_longitude)

		region = world.loc[world_names.isin(selected_countries)]
		minx, miny, maxx, maxy = region.total_bounds
		gdf_filtered = gdf_port.loc[
			(gdf_port.geometry.x >= minx) & (gdf_port.geometry.x <= maxx) &
			(gdf_port.geometry.y >= miny) & (gdf_port.geometry.y <= maxy)
		]
		if display_info:
			print('In Total ', len(gdf_filtered), ' ports are plotted')
		port_list = [self.get_port(id) for id in gdf_filtered['Port']]
		portpool_filtered = PortPool(port_list)
		#
		# Plot the ports
		region2 = world.cx[minx:maxx, miny:maxy]
		fig, ax = plt.subplots()
		ax.set_xlim(minx, maxx)
		ax.set_ylim(miny, maxy)
		region2.plot(ax=ax, color='lightgrey', edgecolor='black')
		gdf_filtered.plot(ax=ax, color='red', markersize = 10)
		for x, y, label in zip(gdf_filtered.geometry.x, gdf_filtered.geometry.y, gdf_filtered['Port']):
			if plot_port_id:
				ax.text(x, y, label, fontsize=10, va='bottom')
		return fig, ax, portpool_filtered

	def get_all_id(self) -> list[str]:
		return [p.get_id() for p in self.__port_list]

	def get_all_pos(self) -> dict:
		re = {}
		for port in self.__port_list:
			re[port.get_id()] = port.get_location()
		return re

	def get_unique_index(self, port: Port) -> int:
		for idx, port_i in enumerate(self.__port_list):
			if port == port_i:
				return idx
		raise ValueError(f'Expect existing port, get "{port.get_id()}"')

	def get_unique_index_by_id(self, port_id: str) -> int:
		for idx, port in enumerate(self.__port_list):
			if port.get_id() == port_id:
				return idx
		raise ValueError(f'Expect existing port, get "{port_id}"')

	def get_port(self, port_id: str) -> Port:
		for port in self.__port_list:
			if port.get_id() == port_id:
				return port
		raise ValueError(f'Expect existing port, get "{port_id}"')

	def get_port_by_name(self, port_name: str) -> Port:
		for port in self.__port_list:
			if port.get_name() == port_name:
				return port
		raise ValueError(f'Expect existing port, get "{port_name}"')

	def get_port_by_idx(self, idx: int) -> Port:
		return self.__port_list[idx]

	def has_port_by_id(self, port_id: str) -> bool:
		for port in self.__port_list:
			if port.get_id() == port_id:
				return True
		return False

	def has_port_by_name(self, port_name: str) -> bool:
		for port in self.__port_list:
			if port.get_name() == port_name:
				return True
		return False

	def add_port(self, port_id: str, name: str, longitude: float, latitude: float,
			fit_vessel_ranks: dict[int, int],
			berth_productivity: dict[int, float],
			cost_portcall: dict[int, float],
			cost_transship: float,
			cost_storage: float,
			transshipment_capacity: bool,
			max_draft: float,
			max_daily_call: int,
			max_line_visit: int=2
		):
		if self.has_port_by_id(port_id):
			return
		self.__port_list.append(
			Port(
				port_id, name, longitude, latitude,
				fit_vessel_ranks,
				berth_productivity,
				cost_portcall,
				cost_transship,
				cost_storage,
				transshipment_capacity,
				max_draft,
				max_daily_call,
				max_line_visit
			)
		)

	def select(self, ports_id: list[str]):
		"""Get a subset of ports by `id`s
		"""
		selected_ports: list[Port] = []
		for port_id in ports_id:
			if self.has_port_by_id(port_id):
				selected_ports.append(self.get_port(port_id))
		return PortPool(selected_ports)

	def filter_by_max_draft(self, draft_req: float) -> list[Port]:
		"""Find all ports whose max draft is greater than `draft`
		"""
		re = []
		for port in self.__port_list:
			if port.max_draft > draft_req:
				re.append(port)
		return re

	def filtered_by_transship_cost(self, cost: float) -> list[Port]:
		"""Find all ports whose transshipment cost is less than `cost`
		"""
		re = []
		for port in self.__port_list:
			if port.cost_transship < cost:
				re.append(port)
		return re

	def filtered_by_transship_capacity(self) -> list[Port]:
		"""Find all ports who can transship
		"""
		re = []
		for port in self.__port_list:
			if port.transshipment_capacity == True:
				re.append(port)
		return re

class PortGraph(PortPool):
	"""class PortGraph

	In addition to the collection of all ports, we also grant the pool some
	additional information, including
		- mutually weekly demand rate
		- mutually distance
	This class is only used in layer 0, the approximation of cost function.
	"""
	__mat_distance: np.ndarray
	__mat_demand: np.ndarray
	__mat_unit_revenue: np.ndarray | None

	def __init__(self, ports_pool: PortPool,
			mat_distance: list[list[float]] | np.ndarray,
			mat_demand: list[list[float]] | np.ndarray,
			mat_unit_revenue: list[list[float]] | np.ndarray | None = None,
			filter_by_demand=True):
		"""
		Input:
			- filter: filter the port pool by demands
		"""
		super().__init__(ports_pool.tolist_port())
		ports_number = self.get_number_of_ports()
		self.__mat_distance = np.array(mat_distance)[:ports_number, :ports_number]
		self.__mat_demand = np.array(mat_demand)[:ports_number, :ports_number]
		if mat_unit_revenue is not None:
			self.__mat_unit_revenue = np.array(mat_unit_revenue)[:ports_number, :ports_number]
		else:
			self.__mat_unit_revenue = None

		if filter_by_demand:
			od_pairs = self.get_all_od_pairs()
			portset = set()
			for od in od_pairs:
				o, d = od
				portset.add(self.get_port_by_idx(o))
				portset.add(self.get_port_by_idx(d))
			sub_ports = list(portset)
			sub_demands = self.get_filtered_demand_matrix(sub_ports)
			sub_distance = self.get_filtered_distance_matrix(sub_ports)
			super().update(sub_ports)
			self.__mat_demand = sub_demands
			self.__mat_distance = sub_distance

	def get_pairs_missing_distance(self) -> list[tuple[int, int]]:
		o_arr, d_arr = np.where(np.isinf(self.__mat_distance))
		pairs = [(o, d) for o, d in zip(o_arr, d_arr)]
		return pairs

	def get_all_od_pairs(self) -> list[tuple[int, int]]:
		"""return a list of index tuples (of ports) that represents the OD pair
		"""
		return list(zip(*np.where(self.__mat_demand > 0)))

	def get_distance(self, port_i: Port, port_j: Port) -> float:
		idx_i = self.get_unique_index(port_i)
		idx_j = self.get_unique_index(port_j)
		return self.__mat_distance[idx_i, idx_j]

	def get_distance_by_id(self, port_i_id: str, port_j_id: str) -> float:
		idx_i = self.get_unique_index_by_id(port_i_id)
		idx_j = self.get_unique_index_by_id(port_j_id)
		return self.__mat_distance[idx_i, idx_j]

	def get_distance_by_idx(self, port_i_idx: int, port_j_idx: int) -> float:
		return self.__mat_distance[port_i_idx, port_j_idx]

	def get_unit_revenue_by_idx(self, port_i_idx: int, port_j_idx: int) -> float | None:
		if self.__mat_unit_revenue is None:
			return None
		else:
			return self.__mat_unit_revenue[port_i_idx, port_j_idx]

	def get_demand_flows(self) -> tuple[np.ndarray, np.ndarray]:
		"""return:
			- inflows of each port
			- outflows of each port
		"""
		inflow = np.sum(self.__mat_demand, axis=0)
		outflow = np.sum(self.__mat_demand, axis=1)
		return inflow, outflow

	def get_demand(self, port_i: Port, port_j: Port) -> float:
		idx_i = self.get_unique_index(port_i)
		idx_j = self.get_unique_index(port_j)
		return self.__mat_demand[idx_i, idx_j]

	def get_demand_by_id(self, port_i_id: str, port_j_id: str) -> float:
		idx_i = self.get_unique_index_by_id(port_i_id)
		idx_j = self.get_unique_index_by_id(port_j_id)
		return self.__mat_demand[idx_i, idx_j]

	def get_demand_by_idx(self, port_i_idx: int, port_j_idx: int) -> float:
		return self.__mat_demand[port_i_idx, port_j_idx]

	def get_filtered_demand_matrix(self, ports: list[Port]) -> np.ndarray:
		indeces = [self.get_unique_index(p) for p in ports]
		return self.__mat_demand[indeces, :][:, indeces]

	def get_filtered_distance_matrix(self, ports: list[Port]) -> np.ndarray:
		indeces = [self.get_unique_index(p) for p in ports]
		return self.__mat_distance[indeces, :][:, indeces]

	def filtered_by_sub_portpool(self, sub_portpool: PortPool):
		indeces: list[int] = []
		for p in sub_portpool.tolist_port():
			if self.has_port_by_id(p.get_id()):
				indeces.append(self.get_unique_index(p))
		sub_mat_demand = self.__mat_demand[indeces, :][:, indeces]
		sub_mat_distance = self.__mat_distance[indeces, :][:, indeces]
		return PortGraph(sub_portpool, sub_mat_distance, sub_mat_demand)

	def plot(self, selected_countries: list[str],
				plot_port_id: bool=False, display_info=False, center_pacific=False,
				demandtype: Literal['in', 'out', 'total']='total',
				odpairs: bool = True, odpairs_color='red'
			) -> Tuple[Figure, Axes, 'PortGraph']:
		# Plot all ports by small red dot
		fig, ax, portpool = super().plot(selected_countries, plot_port_id, display_info, center_pacific)
		portgraph = self.filtered_by_sub_portpool(portpool)
		# Plot the demands of all ports
		inflows, outflows = portgraph.get_demand_flows()
		xs, ys = [], []
		for port in portgraph.tolist_port():
			x, y = port.get_location()
			x = x + 360 if x < 0 else x
			xs.append(x)
			ys.append(y)
		match demandtype:
			case 'in':
				ax.scatter(xs, ys, s=inflows, alpha=0.5)
			case 'out':
				ax.scatter(xs, ys, s=outflows, alpha=0.5)
			case 'total':
				ax.scatter(xs, ys, s=inflows + outflows, alpha=0.3)
		# Plot the connectivity of each od pair
		if not odpairs:
			return fig, ax, portgraph
		od_pairs = portgraph.get_all_od_pairs()
		for od in od_pairs:
			o, d = od
			port_o = portgraph.get_port_by_idx(o)
			port_d = portgraph.get_port_by_idx(d)
			port_o_loc_x, port_o_loc_y = port_o.get_location()
			port_d_loc_x, port_d_loc_y = port_d.get_location()
			port_o_loc_x = port_o_loc_x + 360 if port_o_loc_x < 0 else port_o_loc_x
			port_d_loc_x = port_d_loc_x + 360 if port_d_loc_x < 0 else port_d_loc_x

			arctan_demand = 2 * np.arctan(portgraph.get_demand_by_idx(o, d)) / np.pi
			line = Line2D(
				[port_o_loc_x, port_d_loc_x],
				[port_o_loc_y, port_d_loc_y],
				color=odpairs_color,
				alpha=0.15 * (arctan_demand)**2,
				linewidth=arctan_demand**2
			)
			ax.add_line(line)
		return fig, ax, portgraph
