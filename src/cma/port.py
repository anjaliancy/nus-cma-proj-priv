"""
port.py

Define all port related classes and methods
"""
from typing import Tuple
from importlib import resources
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
from matplotlib.axes import Axes
from shapely.geometry import Point

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
	__n_visit: int

	max_draft: float
	max_daily_call: int
	fit_vessel_ranks: dict[int, float]  # this is not an explicit constraint but more a data limitation constraint
	berth_productivity: list[float]
	cost_call: list[float]
	cost_transship: float
	cost_storage: float
	transshipment_capacity: bool

	def __init__(self, port_id: str, name: str, longitude: float, latitude: float,
					fit_vessel_ranks: dict[int, float], cost_call: list[float], berth_productivity: list[float],
					cost_transship: float, cost_storage: float, transshipment_capacity: bool,
					max_draft: float, max_daily_call: int, number_of_visit: int):
		self.__id = port_id
		self.__name = name
		self.__longitude = longitude
		self.__latitude = latitude
		self.__n_visit = number_of_visit  # max number of visit in a line
		self.max_draft = max_draft
		self.max_daily_call = max_daily_call
		self.fit_vessel_ranks = fit_vessel_ranks
		self.berth_productivity = berth_productivity
		self.cost_call = cost_call
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
		return self.__n_visit

	def get_producticity(self, vesselpool: VesselPool) -> list[float]:
		"""
		Productivity for each vessel type
		"""
		re = []
		for vessel in vesselpool.vessels_list:
			if vessel.vessel_rank in self.fit_vessel_ranks:
				re.append(self.fit_vessel_ranks[vessel.vessel_rank])
			else:
				re.append(0)
		return re

	def get_port_call_costs(self, vesselpool: VesselPool) -> list[float]:
		"""
		Input: all vessels

		Return: a list of port call cost of each vessel
		"""
		n_vessel_types = vesselpool.get_number_of_types()
		pc_costs = [float('inf') for _ in range(n_vessel_types)]
		for vclass, pc_cost in self.fit_vessel_ranks.items():
			pc_costs[vclass - 1] = pc_cost
		return pc_costs

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

	def tolist_port(self) -> list[Port]:
		return self.__port_list

	def get_number_of_ports(self) -> int:
		return len(self.__port_list)

	def plot(self, selected_countries: list[str],
				plot_port_id: bool = False) -> Tuple[Figure, Axes, 'PortPool']:
		"""
		This function input `selected_asia_countries` as a filter and
		return a filtered new collection of ports that is only contained
		in the graph.
		"""
		MAP_FILE_PATH = '110m_cultural/ne_110m_admin_0_countries.shp'
		file = resources.files("cma.res").joinpath(MAP_FILE_PATH)
		geometry = [Point(port.get_location()) for port in self.__port_list]
		gdf = gpd.GeoDataFrame({
			'Port': [port.get_id() for port in self.__port_list],
			'geometry': geometry
			})
		world = gpd.read_file(str(file))
		if not isinstance(world, gpd.GeoDataFrame):
			raise ValueError('Invalid file', file)
		world_names = world['NAME']
		if not isinstance(world_names, pd.Series):
			raise ValueError('Invalid file', file)
		region = world.loc[world_names.isin(selected_countries)]
		minx, miny, maxx, maxy = region.total_bounds
		gdf_filtered = gdf.loc[
			(gdf.geometry.x >= minx) & (gdf.geometry.x <= maxx) &
			(gdf.geometry.y >= miny) & (gdf.geometry.y <= maxy)
		]
		print('In Total ', len(gdf_filtered), ' ports are plotted')
		port_list = [self.get_port(id) for id in gdf_filtered['Port']]
		portpool_filtered = PortPool(port_list)
		#
		# Plot the ports
		fig, ax = plt.subplots()
		region.plot(ax=ax, color='lightgrey', edgecolor='black')
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
					fit_vessel_ranks: dict, cost_call: list[float], berth_productivity: list[float],
					cost_transship: float, cost_storage: float, transshipment_capacity: bool,
					max_draft: float, max_daily_call: int, number_of_visit: int):
		if self.has_port_by_id(port_id):
			return
		self.__port_list.append(
			Port(
				port_id, name, longitude, latitude,
				fit_vessel_ranks, cost_call, berth_productivity,
				cost_transship, cost_storage, transshipment_capacity,
				max_draft, max_daily_call, number_of_visit
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
	__mat_distance: np.matrix
	__mat_demand: np.matrix

	def __init__(self, ports_pool: PortPool,
			mat_distance: list[list[float]] | np.matrix,
			mat_demand: list[list[float]] | np.matrix):
		super().__init__(ports_pool.tolist_port())
		ports_number = self.get_number_of_ports()
		self.__mat_distance = np.matrix(mat_distance)[:ports_number, :ports_number]
		self.__mat_demand = np.matrix(mat_demand)[:ports_number, :ports_number]

	def get_distance(self, port_i: Port, port_j: Port) -> float:
		idx_i = self.get_unique_index(port_i)
		idx_j = self.get_unique_index(port_j)
		return self.__mat_distance[idx_i, idx_j]

	def get_distance_by_id(self, port_i_id: str, port_j_id: str) -> float:
		idx_i = self.get_unique_index_by_id(port_i_id)
		idx_j = self.get_unique_index_by_id(port_j_id)
		return self.__mat_distance[idx_i, idx_j]

	def get_distance_by_idx(self, port_i_idx: int, port_j_idx: int) -> float:
		return self.__mat_distance[port_i_idx][port_j_idx]

	def get_demand_by_id(self, port_i_id: str, port_j_id: str) -> float:
		idx_i = self.get_unique_index_by_id(port_i_id)
		idx_j = self.get_unique_index_by_id(port_j_id)
		return self.__mat_demand[idx_i, idx_j]

	def get_demand_by_idx(self, port_i_idx: int, port_j_idx: int) -> float:
		return self.__mat_demand[port_i_idx, port_j_idx]

	def get_all_od_pairs(self) -> list[tuple[int, int]]:
		"""return a list of index tuples (of ports) that represents the OD pair
		"""
		return list(zip(*np.where(self.__mat_demand > 0)))
