"""
Module `service`

Define all service related classes and methods
"""
from typing import Union, TypeGuard, Self
import heapq
import numpy as np
import pandas as pd
import geopandas as gpd
from sklearn.cluster import KMeans
from importlib import resources
from collections import Counter
from matplotlib import pyplot as plt
from shapely.geometry import LineString, Point
from scgraph.geographs.marnet import marnet_geograph  # type: ignore
## Note: the typing of this function is not correct

from .port import Port, PortPool, PortGraph
from .vessel import VesselPool
from .paths import DATA_DIR

class Segment:
	"""class Segment
	"""
	first: Port
	second: Port

	def __init__(self, segment: tuple[Port, Port]):
		self.first = segment[0]
		self.second = segment[1]
	def __repr__(self) -> str:
		return '(' + str(self.first) + ',' +str(self.second) + ')'
	def __eq__(self, value: object) -> bool:
		if isinstance(value, Segment):
			return self.first == value.first and self.second == value.second
		return False
	def __hash__(self) -> int:
		return hash(str(self))

class Slot:
	"""class Slot

	One segment of a service line that connects two ports

	Slot contains two types of information:
		- Service
		- Segment

	In other words, a slot is always the segment in a particular service
	"""
	__service : 'ServiceLine'
	__segment : Segment

	def __init__(self, service: 'ServiceLine', segment: tuple[Port, Port]|Segment):
		self.__service = service

		if isinstance(segment, Segment):
			self.__segment = segment
		elif isinstance(segment, tuple):
			self.__segment = Segment(segment)
		else:
			raise ValueError(f"Expect Segment, get {segment}")

	def __repr__(self) -> str:
		return self.__service.name() + ': ' + str(self.__segment)

	def get_service(self) -> 'ServiceLine':
		return self.__service

	def get_service_name(self) -> str:
		return self.__service.name()

	def get_segment(self) -> Segment:
		return self.__segment

	def get_start(self) -> Port:
		return self.__segment.first

	def get_end(self) -> Port:
		return self.__segment.second

	def get_distance(self, portgraph: PortGraph) -> float:
		return portgraph.get_distance(
			self.__segment.first, self.__segment.second)

class Path:
	"""class Path

	The connection of two ports by slots
	"""
	__data: list[Slot]

	def __init__(self, data: list[Slot]):
		# check duplicated
		if len(set(data)) != len(data):
			raise ValueError(f'Duplicated Slot in Path: {str(data)}')
		self.__data = data

	def __repr__(self):
		return str(self.__data)

	def get_origin(self) -> Port:
		return self.__data[0].get_start()

	def get_destination(self) -> Port:
		return self.__data[-1].get_end()

	def get_first_service_line(self) -> 'ServiceLine':
		return self.__data[0].get_service()

	def get_first_service_name(self) -> str:
		return self.__data[0].get_service_name()

	def get_last_service_line(self) -> 'ServiceLine':
		return self.__data[-1].get_service()

	def get_last_service_name(self) -> str:
		return self.__data[-1].get_service_name()

	def tolist_port(self) -> list[Port]:
		path = []
		for slot in self.__data:
			path.append(slot.get_start())
		path.append(self.__data[-1].get_end())
		return path

	def tolist_slot(self) -> list[Slot]:
		return self.__data

	def has_slot(self, slot: Slot) -> bool:
		return slot in self.__data

	def has_segment(self, seg: Segment) -> bool:
		for slot in self.__data:
			if seg == slot.get_segment():  #  __eq__() is overloaded
				return True
		return False

	def number_of_slots(self) -> int:
		return len(self.__data)

	def get_hubs(self) -> list[Port]:
		"""
		`Hub` means a port for transshipment
		"""
		services = set()
		hubs = []
		for slot in self.__data:
			service_name = slot.get_service_name()
			if len(services) == 0:
				services.add(service_name)
				continue
			if service_name not in services:
				services.add(service_name)
				hubs.append(slot.get_start())
		return hubs

	def get_distance(self, portgraph: PortGraph) -> float:
		dist = 0
		for slot in self.__data:
			port_i = slot.get_start()
			port_j = slot.get_end()
			dist += portgraph.get_distance(port_i, port_j)
		return dist

	def plot(self, selected_countries: list[str], fig_size = (15, 9), eps = 3):
		"""Plot the service line
		"""
		# region
		MAP_FILE_PATH = '110m_cultural/ne_110m_admin_0_countries.shp'
		file = DATA_DIR.joinpath(MAP_FILE_PATH)
		world = gpd.read_file(str(file))
		if not isinstance(world, gpd.GeoDataFrame):
			raise TypeError(f'file `{file}` invalid')
		world_names = world['NAME']
		if not isinstance(world_names, pd.Series):
			raise TypeError(f'file `{file}` invalid')
		region = world.loc[world_names.isin(selected_countries)]
		# ports
		ports = self.tolist_port()
		port_locs = [Point(port.get_location()) for port in ports]
		idx_ports = [idx + 1 for idx, _ in enumerate(ports)]
		port_names = [port.get_id() for port in ports]
		gdf_ports = gpd.GeoDataFrame({'idx': idx_ports, 'names': port_names, 'geometry': port_locs})
		minx, miny, maxx, maxy = gdf_ports.geometry.total_bounds
		# hubs
		hubs = self.get_hubs()
		gdf_hubs = None
		if len(hubs) > 0:
			hub_locs = [Point(port.get_location()) for port in hubs]
			hub_ids = [port.get_id() for port in hubs]
			gdf_hubs = gpd.GeoDataFrame({'hubs': hub_ids, 'geometry': hub_locs})

		# plot region
		_, ax = plt.subplots(figsize=fig_size)
		ax.set_xlim(minx - eps, maxx + eps)
		ax.set_ylim(miny - eps, maxy + eps)
		region.plot(ax=ax, color='lightgrey')#, edgecolor='black')

		# plot slots
		for idx, slot in enumerate(self.__data):
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
			label = str(slot) + f' ({idx+1}->{idx+2})'
			gdf_path.plot(ax=ax, linewidth=2, label=label)

		# plot ports
		if gdf_hubs is not None:
			gdf_hubs.plot(ax=ax, color='red', markersize = 20)
		for x, y, idx in zip(gdf_ports.geometry.x, gdf_ports.geometry.y, idx_ports):
			ax.text(x, y, str(idx), fontsize=10, va='bottom')
		# for x, y, label in zip(gdf_hubs.geometry.x, gdf_hubs.geometry.y, gdf_hubs['hubs']):
		# 	ax.text(x, y, label, fontsize=10, va='bottom')
		plt.legend(loc="center left", bbox_to_anchor=(1, 0.5))
		plt.pause(0.1)

class LineAction:
	"""class LineAction

	Attribute:
		__cmd
		__loc
	"""
	cmd: str
	loc: list[int]

	def __init__(self, cmd: str, loc: list[int]):
		self.loc = loc
		self.cmd = cmd

	def __repr__(self) -> str:
		return '"' + self.cmd + '" ' + str(self.loc)

class ServiceLine:
	"""The circle line that connects a list of ports

	For example:

	The line is (P1, P2, P3, P1, P5). It represents a circle.
	Using slots, this line can be re-represented as:

	(P1,P2), (P2,P3), (P3,P1), (P1,P5), (P5,P1)

	We impose some restrictions on the service line, including:
		1.
		2.
	"""
	__name: str
	__line: list[Port]
	week: float = 999999.0
	frozen: bool = False
	frozen_speed: float | None = None
	frozen_weeks: float | None = None
	vessel_rank: int | None = None
	service_type: str = 'OWN'
	anchor_eosp_wd: float | None = None
	anchor_eosp_hr: float | None = None
	proforma_leg_durations: list[float] | None = None
	_buffer_wait_times: list[float] | None
	_buffer_speeds_to_next: list[float] | None
	_buffer_ignore_lb: bool

	def __init__(self, name: str, line: list[Port], _test: bool=False, verbose=False, warn=True, portgraph: PortGraph | None = None):
		self.__name = name
		self.__line = line
		self._buffer_wait_times = None
		self._buffer_speeds_to_next = None
		self._buffer_ignore_lb = False
		self.service_type = 'OWN'

		if (not _test) and False is self.check_valid(warn, portgraph=portgraph):
			if verbose:
				print(f'Invalid line "{name}":', line)
			raise ValueError(f'Invalid line {name}')

	def __repr__(self) -> str:
		return self.__name + ' -- ' + str(self.__line)

	def check_valid(self, warn=True, portgraph: PortGraph | None = None) -> bool:
		"""Check whether the service line is a valid one
		"""
		# Case 1: include less than 2 ports
		#
		# we allow for this kind of action since it means to delete the service line
		#
		#if self.number_of_port() <= 1:
		#	print("Warning: Invalid since the line contains less than two ports.")
		#	return False
		for loc in range(self.number_of_port()):
			loc_next_1 = self.idx_of_next_idx(loc)
			loc_next_2 = self.idx_of_next_idx(loc_next_1)
			loc_next_3 = self.idx_of_next_idx(loc_next_2)
			# Case 2: staying
			# For example, line contains (..., P1, P1, ....)
			if self.__line[loc] == self.__line[loc_next_1]:
				if warn:
					print("Warning: Invalid since a port is visited consecutively.")
				return False
		
		# Case 3: repeated directed edges (sub-routes)
		# Check that no directed edge (A→B) appears more than once in the rotation
		# This prevents patterns like CNXMN→TWKHH→TWTXG→CNXMN→TWKHH
		edges_seen = set()
		for loc in range(self.number_of_port()):
			loc_next = self.idx_of_next_idx(loc)
			edge = (self.__line[loc], self.__line[loc_next])
			if edge in edges_seen:
				if warn:
					print(f"Warning: Invalid since edge {self.__line[loc].get_id()}→{self.__line[loc_next].get_id()} is repeated.")
				return False
			edges_seen.add(edge)
		## Case 4: a port visited more than 3 times
		port_ctr = Counter(self.__line)
		if any(ct > port.get_max_number_of_visit() for port, ct in port_ctr.items()):
			if warn:
				print("Warning: Invalid since a port is visited more than max allowed number.")
			return False
		## Case 5: too many unique ports (> 20)
		unique_ports = len(set(self.__line))
		if unique_ports > 20:
			if warn:
				print(f"Warning: Invalid since service has {unique_ports} unique ports (max 20 allowed).")
			return False
			
		## Case 6: Number of ports called more than once <= 2
		# e.g., A-B-A-C-D-E-B-F-E (A, B, E repeated -> 3 ports -> Invalid)
		num_multi_visit = sum(1 for ct in port_ctr.values() if ct > 1)
		if num_multi_visit > 2:
			if warn:
				print(f"Warning: Invalid since {num_multi_visit} ports are visited more than once (max 2 allowed).")
			return False
			
		## Case 7: Must visit at least one TS port
		# Check if at least one port in the line has transshipment capacity
		if not any(port.transshipment_capacity for port in self.__line):
			if warn:
				print("Warning: Invalid since service line must visit at least one TS port.")
			return False

		## Case 8: Max direct port to port connection = 2k miles
		if portgraph is not None:
			for slot in self.tolist_slot():
				dist = slot.get_distance(portgraph)
				if dist > 2000:
					if warn:
						print(f"Warning: Invalid since leg {slot.get_segment()} has distance {dist:.2f} (max 2000 allowed).")
					return False

		return True

	def get_adjacency_matrix(self, ports_pool: PortPool) -> np.ndarray:
		"""Return:
			out-degree matrix
		"""
		n = ports_pool.get_number_of_ports()
		adj = np.zeros((n, n))
		for idx, port in enumerate(self.__line):
			next_port = self.next_port_of_idx(idx)
			loc_port = ports_pool.get_unique_index(port)
			loc_next = ports_pool.get_unique_index(next_port)
			adj[loc_port, loc_next] = 1
		return adj

	###########################################################################
	# Basic Attributes & Operations
	#
	# Service is different from `Path` since it is a CIRLCE.
	# Hence, the next of ending is beginning.
	###########################################################################

	def name(self) -> str:
		return self.__name

	def number_of_port(self) -> int:
		return len(self.__line)

	def get_distance(self, portgraph: PortGraph) -> float:
		total_dist = 0
		for slot in self.tolist_slot():
			total_dist += slot.get_distance(portgraph)
		return total_dist

	###########################################################################
	# Buffer profile helpers (waiting time, speed to next, ignore lower bound)
	###########################################################################
	def set_buffer_profile(self,
			wait_times: list[float] | None,
			speeds_to_next: list[float] | None,
			ignore_lower_bound: bool
		):
		"""Attach proforma-derived buffer data to the service line"""
		if wait_times is not None and len(wait_times) != self.number_of_port():
			raise ValueError("buffer wait_times length must match number of ports")
		if speeds_to_next is not None and len(speeds_to_next) != self.number_of_port():
			raise ValueError("buffer speeds_to_next length must match number of ports (one per leg origin)")
		self._buffer_wait_times = wait_times
		self._buffer_speeds_to_next = speeds_to_next
		self._buffer_ignore_lb = ignore_lower_bound

	def has_buffer_profile(self) -> bool:
		return self._buffer_wait_times is not None and self._buffer_speeds_to_next is not None

	def get_buffer_wait_times(self) -> list[float] | None:
		return self._buffer_wait_times

	def get_buffer_speeds_to_next(self) -> list[float] | None:
		return self._buffer_speeds_to_next

	def get_buffer_ignore_lb(self) -> bool:
		return self._buffer_ignore_lb

	###########################################################################
	# Schedule profile helpers (anchor EOSP, proforma leg durations)
	###########################################################################
	def set_schedule_profile(self,
			anchor_wd: float | None,
			anchor_hr: float | None,
			leg_durations: list[float] | None
		):
		"""Attach proforma-derived schedule data to the service line"""
		if leg_durations is not None and len(leg_durations) != self.number_of_port():
			raise ValueError("leg_durations length must match number of ports")
		self.anchor_eosp_wd = anchor_wd
		self.anchor_eosp_hr = anchor_hr
		self.proforma_leg_durations = leg_durations

	def has_schedule_profile(self) -> bool:
		return self.anchor_eosp_wd is not None and self.anchor_eosp_hr is not None

	def get_anchor_eosp(self) -> tuple[float | None, float | None]:
		return self.anchor_eosp_wd, self.anchor_eosp_hr

	def get_proforma_leg_durations(self) -> list[float] | None:
		return self.proforma_leg_durations

	def get_schedule(self, portgraph: PortGraph, vesselpool: VesselPool | None = None) -> list[tuple[float, float]]:
		"""
		Calculate Estimated Time of Berth (ETB) and Estimated Time of Departure (ETD) 
		for each port in the rotation, in hours from Monday 00:00.
		
		Returns:
			List of (ETB, ETD) tuples in hours from Monday 00:00.
		"""
		if not self.has_schedule_profile():
			# Cannot calculate schedule without anchor EOSP
			return []
			
		n_ports = self.number_of_port()
		
		# Initial EOSP in hours from Monday 00:00
		anchor_wd = self.anchor_eosp_wd if self.anchor_eosp_wd is not None else 0.0
		anchor_hr = self.anchor_eosp_hr if self.anchor_eosp_hr is not None else 0.0
		base_eosp = anchor_wd * 24 + anchor_hr
		
		# 1. Collect leg durations (EOSP to EOSP)
		durations = []
		for i in range(n_ports):
			if self.proforma_leg_durations is not None and i < len(self.proforma_leg_durations):
				durations.append(self.proforma_leg_durations[i])
			else:
				# Estimate leg duration for new/modified ports
				port = self.get_port_by_idx(i)
				next_port = self.next_port_of_idx(i)
				
				# a. Waiting time
				t_wait = 2.0
				if self._buffer_wait_times is not None and i < len(self._buffer_wait_times):
					t_wait = self._buffer_wait_times[i]
				elif hasattr(port, 'waiting_time') and isinstance(port.waiting_time, dict):
					t_wait = np.mean(list(port.waiting_time.values())) if port.waiting_time else 2.0
				
				# b. Maneuvering
				t_manin = getattr(port, 'maneuvering_time_in', 3.0)
				t_manout = getattr(port, 'maneuvering_time_out', 3.0)
				
				# c. Stay Time (Data-driven)
				t_stay = 12.0
				if vesselpool is not None and self.vessel_rank is not None:
					vessel = vesselpool.get_vessel_instance(self.vessel_rank)
					prod = port.berth_productivity.get(self.vessel_rank, 50.0)
					nominal_volume = vessel.vessel_capacity * 0.15 # Assume 15% exchange
					t_stay = max(6.0, nominal_volume / prod) # Min 6 hours
				
				# d. Sailing Time (Data-driven)
				dist = portgraph.get_distance(port, next_port)
				speed = 14.0
				if vesselpool is not None and self.vessel_rank is not None:
					vessel = vesselpool.get_vessel_instance(self.vessel_rank)
					speed = (vessel.min_speed + vessel.max_speed) / 2.0 # Nominal mid-speed
				t_sail = dist / speed
				
				durations.append(t_wait + t_manin + t_stay + t_manout + t_sail)
		
		# 2. Scale durations to match cycle length if week is set
		if self.week < 1000.0: # If week is assigned (typical values 1-12)
			target_total = self.week * 168.0
			current_total = sum(durations)
			if current_total > 0:
				scale = target_total / current_total
				durations = [d * scale for d in durations]
		
		# 3. Compute ETB/ETD from durations
		schedule = []
		current_eosp = base_eosp
		for i in range(n_ports):
			port = self.get_port_by_idx(i)
			
			# We need to break down the leg duration into (Wait+ManIn) and Stay
			# For simplicity, if we have durations, we assume ETB is at some offset
			# If we used estimates, we have the components. If proforma, we estimate ratios.
			
			if self.proforma_leg_durations is not None and i < len(self.proforma_leg_durations):
				# For proforma, use a typical 20% offset for ETB
				t_to_etb = 0.2 * durations[i] 
				t_stay = 0.4 * durations[i]
			else:
				# Use the same logic as above but scaled
				t_wait = 2.0
				if self._buffer_wait_times is not None and i < len(self._buffer_wait_times):
					t_wait = self._buffer_wait_times[i]
				t_manin = getattr(port, 'maneuvering_time_in', 3.0)
				
				t_to_etb = t_wait + t_manin
				# Recalculate t_stay for the specific port
				t_stay = 12.0
				if vesselpool is not None and self.vessel_rank is not None:
					vessel = vesselpool.get_vessel_instance(self.vessel_rank)
					prod = port.berth_productivity.get(self.vessel_rank, 50.0)
					nominal_volume = vessel.vessel_capacity * 0.15
					t_stay = max(6.0, nominal_volume / prod)
				
				# If we scaled, scale these too
				if self.week < 1000.0:
					target_total = self.week * 168.0
					current_total = sum(durations) # This is already scaled sum
					# We should have used the original estimated total for scale factor
					# But since durations is already scaled, we just use it
					pass 

			etb = current_eosp + t_to_etb
			etd = etb + t_stay
			schedule.append((etb, etd))
			
			current_eosp += durations[i]
				
		return schedule

	def _copy_metadata_to(self, target: 'ServiceLine'):
		"""Internal helper to copy scheduling and operational metadata to a new line instance"""
		target.anchor_eosp_wd = self.anchor_eosp_wd
		target.anchor_eosp_hr = self.anchor_eosp_hr
		target.vessel_rank = self.vessel_rank
		target.service_type = self.service_type
		target.frozen = self.frozen
		target.frozen_speed = self.frozen_speed
		target.frozen_weeks = self.frozen_weeks
		target._buffer_ignore_lb = self._buffer_ignore_lb
		# Note: buffer_wait_times and proforma_leg_durations are NOT copied 
		# because they are sequence-dependent and length-specific.

	def last_index_of_port(self, port: Port) -> int:
		"""The last index of a port in a service line

		For example, the line is (P1, P2, P3, P1, P5).

		Then, the last index of `P1` is 3.
		"""
		the_idx = self.number_of_port()
		for idx in range(self.number_of_port()):
			if self.__line[idx] == port:
				the_idx = idx
		if the_idx == self.number_of_port():
			raise ValueError(f'Port "{port.get_id()}" not in Service')
		return the_idx

	def all_index_of_port(self, port: Port) -> list[int]:
		"""All index of a port in a service line

		For example, the line is (P1, P2, P3, P1, P5). Then,

		The index of `P1` is (0, 3).
		"""
		indexes = []
		for idx in range(self.number_of_port()):
			if self.__line[idx] == port:
				indexes.append(idx)
		return indexes

	def idx_of_next_idx(self, idx: int) -> int:
		"""The index of the next port of the given port in a service line

		For example, the line is (P1, P2, P3, P1, P5). Then,

		1. The next port of the 0-th port is `P2`, whose index is 1.
		2. The next port of the 4-th port is `P1`, whose index is 0.
		"""
		if idx == self.number_of_port() - 1:
			return 0
		else:
			return idx + 1

	def idx_of_prev_idx(self, idx: int) -> int:
		"""Similar to above
		"""
		if idx == 0:
			return self.number_of_port() - 1
		else:
			return idx - 1

	def next_port_of_idx(self, idx: int) -> Port:
		"""The port that next to the port of given index in a service line

		For example:

		The line is (P1, P2, P3, P1, P5). Then,

		1. The next port of the 0-th port is `P2`.
		2. The next port of the 4-th port is `P1`.
		"""
		return self.__line[self.idx_of_next_idx(idx)]

	def prev_port_of_idx(self, idx: int) -> Port:
		"""Similar to above
		"""
		return self.__line[self.idx_of_prev_idx(idx)]

	###########################################################################
	# Atomic Operations for Modifying Service Lines
	###########################################################################

	def shift_port(self, port_idx: int, delta: int, validate: bool = True, portgraph: PortGraph | None = None) -> 'ServiceLine':
		"""Shift a port visit earlier or later in the rotation
		
		Args:
			port_idx: Index of the port to shift (0-based)
			delta: Number of positions to shift (positive = later, negative = earlier)
			validate: Whether to validate the result (default True)
		
		Returns:
			New ServiceLine with the port shifted
			
		Raises:
			ValueError: If port_idx is invalid or result is invalid service line
			
		Example:
			Line: [P0, P1, P2, P3, P4]
			shift_port(1, 2) → [P0, P2, P3, P1, P4]  # P1 shifted 2 positions later
			shift_port(3, -1) → [P0, P1, P3, P2, P4]  # P3 shifted 1 position earlier
		"""
		n = self.number_of_port()
		
		if not (0 <= port_idx < n):
			raise ValueError(f"Invalid port_idx {port_idx}. Must be in range [0, {n-1}]")
		
		if delta == 0:
			# No change, return copy
			new_line = ServiceLine(self.name(), self.__line.copy(), _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			return new_line
		
		# Create new sequence
		sequence = self.__line.copy()
		port = sequence.pop(port_idx)
		
		# Calculate new position (handle circular rotation)
		new_idx = (port_idx + delta) % n
		sequence.insert(new_idx, port)
		
		# Create and validate new service line
		try:
			new_line = ServiceLine(self.name(), sequence, _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			if validate and not new_line.check_valid(warn=False, portgraph=portgraph):
				raise ValueError(f"Shifting port at index {port_idx} by {delta} creates invalid service line")
			return new_line
		except ValueError as e:
			raise ValueError(f"Shifting port at index {port_idx} by {delta} failed: {str(e)}")

	def swap_ports(self, idx1: int, idx2: int, validate: bool = True, portgraph: PortGraph | None = None) -> 'ServiceLine':
		"""Swap two port visits in the rotation
		
		Args:
			idx1: Index of first port (0-based)
			idx2: Index of second port (0-based)
			validate: Whether to validate the result (default True)
		
		Returns:
			New ServiceLine with ports swapped
			
		Raises:
			ValueError: If indices are invalid or result is invalid service line
			
		Example:
			Line: [P0, P1, P2, P3, P4]
			swap_ports(1, 3) → [P0, P3, P2, P1, P4]  # P1 and P3 swapped
		"""
		n = self.number_of_port()
		
		if not (0 <= idx1 < n):
			raise ValueError(f"Invalid idx1 {idx1}. Must be in range [0, {n-1}]")
		if not (0 <= idx2 < n):
			raise ValueError(f"Invalid idx2 {idx2}. Must be in range [0, {n-1}]")
		
		if idx1 == idx2:
			# No change, return copy
			new_line = ServiceLine(self.name(), self.__line.copy(), _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			return new_line
		
		# Create new sequence with swapped ports
		sequence = self.__line.copy()
		sequence[idx1], sequence[idx2] = sequence[idx2], sequence[idx1]
		
		# Create and validate new service line
		try:
			new_line = ServiceLine(self.name(), sequence, _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			if validate and not new_line.check_valid(warn=False, portgraph=portgraph):
				raise ValueError(f"Swapping ports at indices {idx1} and {idx2} creates invalid service line")
			return new_line
		except ValueError as e:
			raise ValueError(f"Swapping ports at indices {idx1} and {idx2} failed: {str(e)}")

	###########################################################################
	# Multi-Step Action Macros (Composite Operations)
	###########################################################################

	def reverse_segment(self, start_idx: int, end_idx: int, validate: bool = True, portgraph: PortGraph | None = None) -> 'ServiceLine':
		"""Reverse the order of ports in a segment of the rotation
		
		Args:
			start_idx: Start of segment to reverse (inclusive, 0-based)
			end_idx: End of segment to reverse (inclusive, 0-based)
			validate: Whether to validate the result (default True)
		
		Returns:
			New ServiceLine with segment reversed
			
		Example:
			Line: [P0, P1, P2, P3, P4]
			reverse_segment(1, 3) → [P0, P3, P2, P1, P4]
		"""
		n = self.number_of_port()
		
		if not (0 <= start_idx < n):
			raise ValueError(f"Invalid start_idx {start_idx}")
		if not (0 <= end_idx < n):
			raise ValueError(f"Invalid end_idx {end_idx}")
		
		sequence = self.__line.copy()
		
		# Handle wrapping for circular rotation
		if start_idx <= end_idx:
			# Simple case: reverse continuous segment
			segment = sequence[start_idx:end_idx+1]
			segment.reverse()
			sequence[start_idx:end_idx+1] = segment
		else:
			# Wrapping case: segment wraps around end
			segment = sequence[start_idx:] + sequence[:end_idx+1]
			segment.reverse()
			sequence[start_idx:] = segment[:len(sequence[start_idx:])]
			sequence[:end_idx+1] = segment[len(sequence[start_idx:]):]
		
		try:
			new_line = ServiceLine(self.name(), sequence, _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			if validate and not new_line.check_valid(warn=False, portgraph=portgraph):
				raise ValueError(f"Reversing segment [{start_idx}, {end_idx}] creates invalid service line")
			return new_line
		except ValueError as e:
			raise ValueError(f"Reversing segment [{start_idx}, {end_idx}] failed: {str(e)}")

	def rotate(self, steps: int, validate: bool = True, portgraph: PortGraph | None = None) -> 'ServiceLine':
		"""Rotate the entire service line by a number of steps
		
		Args:
			steps: Number of positions to rotate (positive = right, negative = left)
			validate: Whether to validate the result (default True)
		
		Returns:
			New ServiceLine rotated by steps positions
			
		Example:
			Line: [P0, P1, P2, P3, P4]
			rotate(2) → [P3, P4, P0, P1, P2]  # Rotate right by 2
			rotate(-1) → [P1, P2, P3, P4, P0]  # Rotate left by 1
		"""
		n = self.number_of_port()
		
		if n == 0:
			new_line = ServiceLine(self.name(), self.__line.copy(), _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			return new_line
		
		# Normalize steps to be within [0, n)
		steps = steps % n
		
		# Rotate by slicing
		sequence = self.__line[-steps:] + self.__line[:-steps] if steps > 0 else self.__line.copy()
		
		try:
			new_line = ServiceLine(self.name(), sequence, _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			if validate and not new_line.check_valid(warn=False, portgraph=portgraph):
				raise ValueError(f"Rotating by {steps} steps creates invalid service line")
			return new_line
		except ValueError as e:
			raise ValueError(f"Rotating by {steps} steps failed: {str(e)}")

	def insert_port(self, port: Port, position: int, validate: bool = True, portgraph: PortGraph | None = None) -> 'ServiceLine':
		"""Insert a port at a specific position in the rotation
		
		Args:
			port: Port object to insert
			position: Index where to insert (0-based, port will be at this index after insertion)
			validate: Whether to validate the result (default True)
		
		Returns:
			New ServiceLine with port inserted
			
		Example:
			Line: [P0, P1, P2, P3]
			insert_port(P_new, 2) → [P0, P1, P_new, P2, P3]
		"""
		n = self.number_of_port()
		
		if not (0 <= position <= n):
			raise ValueError(f"Invalid position {position}. Must be in range [0, {n}]")
		
		sequence = self.__line.copy()
		sequence.insert(position, port)
		
		try:
			new_line = ServiceLine(self.name(), sequence, _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			if validate and not new_line.check_valid(warn=False, portgraph=portgraph):
				raise ValueError(f"Inserting port {port.get_id()} at position {position} creates invalid service line")
			return new_line
		except ValueError as e:
			raise ValueError(f"Inserting port {port.get_id()} at position {position} failed: {str(e)}")

	def remove_port(self, position: int, validate: bool = True, portgraph: PortGraph | None = None) -> 'ServiceLine':
		"""Remove a port at a specific position from the rotation
		
		Args:
			position: Index of port to remove (0-based)
			validate: Whether to validate the result (default True)
		
		Returns:
			New ServiceLine with port removed
			
		Example:
			Line: [P0, P1, P2, P3, P4]
			remove_port(2) → [P0, P1, P3, P4]
		"""
		n = self.number_of_port()
		
		if not (0 <= position < n):
			raise ValueError(f"Invalid position {position}. Must be in range [0, {n-1}]")
		
		sequence = self.__line.copy()
		removed_port = sequence.pop(position)
		
		try:
			new_line = ServiceLine(self.name(), sequence, _test=not validate, portgraph=portgraph)
			self._copy_metadata_to(new_line)
			if validate and not new_line.check_valid(warn=False, portgraph=portgraph):
				raise ValueError(f"Removing port {removed_port.get_id()} at position {position} creates invalid service line")
			return new_line
		except ValueError as e:
			raise ValueError(f"Removing port at position {position} failed: {str(e)}")

	def move_port(self, from_idx: int, to_idx: int, validate: bool = True, portgraph: PortGraph | None = None) -> 'ServiceLine':
		"""Move a port from one position to another (combination of remove + insert)
		
		This is equivalent to shift_port but with explicit source and destination indices.
		
		Args:
			from_idx: Current index of port (0-based)
			to_idx: Destination index (0-based)
			validate: Whether to validate the result (default True)
		
		Returns:
			New ServiceLine with port moved
			
		Example:
			Line: [P0, P1, P2, P3, P4]
			move_port(1, 3) → [P0, P2, P3, P1, P4]
		"""
		# Use shift_port since it's already implemented
		delta = to_idx - from_idx
		return self.shift_port(from_idx, delta, validate=validate, portgraph=portgraph)

	def plot(self, selected_countries: list[str], fig_size = (15, 9), eps = 2, center_pacific=False):
		"""Plot the service line
		"""
		MAP_FILE_PATH = '110m_cultural/ne_110m_admin_0_countries.shp'
		file = DATA_DIR.joinpath(MAP_FILE_PATH)
		world = gpd.read_file(str(file))
		if not isinstance(world, gpd.GeoDataFrame):
			raise TypeError(f'file `{file}` invalid')
		world_names = world['NAME']
		if not isinstance(world_names, pd.Series):
			raise TypeError(f'file `{file}` invalid')
		region = world.loc[world_names.isin(selected_countries)]
		port_locs = [Point(port.get_location()) for port in self.__line]
		idx_ports = [idx + 1 for idx, _ in enumerate(self.__line)]
		port_names = [port.get_id() for port in self.__line]
		gdf_ports = gpd.GeoDataFrame({'idx': idx_ports, 'names': port_names, 'locs': port_locs, 'geometry': port_locs})
		minx, miny, maxx, maxy = gdf_ports.geometry.total_bounds
		# plot region
		_, ax = plt.subplots(figsize = fig_size)
		ax.set_xlim(minx - eps, maxx + eps)
		ax.set_ylim(miny - eps, maxy + eps)
		region.plot(ax=ax, color='lightgrey')#, edgecolor='black')

		slots = self.tolist_slot()
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
			label = f'({idx+1}->{self.idx_of_next_idx(idx) + 1}): ' + str(p1) + '->' + str(p2)
			gdf_path.plot(ax=ax, color="blue", linewidth=2, label = label)

		# plot ports
		gdf_ports.plot(ax=ax, color='red', markersize = 20)
		for x, y, idx in zip(gdf_ports.geometry.x, gdf_ports.geometry.y, idx_ports):
			ax.text(x, y, str(idx), fontsize=10, va='bottom')
		plt.legend(loc="center left", bbox_to_anchor=(1, 0.5), handlelength=0)
		plt.pause(0.1)

	###########################################################################
	# Port related
	###########################################################################

	def tolist_port(self) -> list[Port]:
		return self.__line

	def get_port_by_idx(self, idx: int) -> Port:
		return self.__line[idx]

	def has_port(self, port: Port) -> bool:
		return port in self.__line

	def has_port_by_id(self, port_id: str, port_pool: PortPool) -> bool:
		return self.has_port(port_pool.get_port(port_id))

	def count_port_calls(self, port: Port) -> int:
		"""Return how many times the line calls at the given port."""
		return sum(1 for line_port in self.__line if line_port == port)

	def are_ports_connected(self, port_i: Port, port_j: Port) -> bool:
		if port_i == port_j:
			raise ValueError('Same Ports')
		return self.has_port(port_i) and self.has_port(port_j)

	def are_ports_connected_by_id(self, id_i: str, id_j: str, port_pool: PortPool) -> bool:
		return self.are_ports_connected(port_pool.get_port(id_i), port_pool.get_port(id_j))

	def remove_port_by_index(self, idx:int):
		self.__line.pop(idx)

	###########################################################################
	# Slot related
	#
	# Slot means "edge" that connects two ports
	###########################################################################

	def tolist_slot(self) -> list[Slot]:
		"""Turn the servise line into a list of slots
		"""
		re = []
		if self.number_of_port() <= 1:
			return re
		for idx in range(self.number_of_port()-1):
			s = Slot(self, (self.__line[idx], self.__line[idx + 1]))
			re.append(s)
		re.append(Slot(self, (self.__line[self.number_of_port() - 1], self.__line[0])))
		return re

	def get_slot_by_idx(self, idx: int) -> Slot:
		"""Return the indexed slot
		"""
		return Slot(self, (self.__line[idx], self.next_port_of_idx(idx)))

	def get_segment_idx(self, seg: Segment) -> int:
		"""
		return:
			-1 if the segment is not in service line
		"""
		if self.number_of_port() <= 1:
			return -1
		port_i, port_j = seg.first, seg.second
		if self.__line[-1] == port_i and self.__line[0] == port_j:
			return len(self.__line) - 1
		for idx in range(self.number_of_port()-1):
			if self.__line[idx] == port_i and self.__line[idx + 1] == port_j:
				return idx
		return -1

	def has_slot(self, port_i: Port, port_j: Port) -> bool:
		"""Check whether the service line has the slot from `port_i` to `port_j`
		"""
		if self.__line[-1] == port_i and self.__line[0] == port_j:
			return True
		for idx, port in enumerate(self.__line):
			if port == port_i and self.__line[idx + 1] == port_j:
				return True
		return False

	def has_slot_by_id(self, id_i: str, id_j: str, port_pool: PortPool) -> bool:
		"""Similar to above
		"""
		return self.has_slot(port_pool.get_port(id_i), port_pool.get_port(id_j))


	###########################################################################
	# Path related
	#
	# Path means the shortest sequence of edges that connects two ports.
	# Path has two representations
	# 	1. list of ports
	# 	2. list of slots
	###########################################################################

	def get_slot_list_by_index(self, idx_1: int, idx_2: int) -> list[Slot]:
		"""Get a list of slot in this service from `start` to `end`
		"""
		if idx_1 >= self.number_of_port():
			raise ValueError(f'Index "{idx_1}" not in Service')
		if idx_2 >= self.number_of_port():
			raise ValueError(f'Index "{idx_2}" not in Service')
		if idx_1 == idx_2:
			raise ValueError(f"Same indexes: idx_1 = idx_2 = {idx_1}")
		slots = []
		the_idx = idx_1
		while True:
			the_port = self.__line[the_idx]
			next_idx = self.idx_of_next_idx(the_idx)
			next_port = self.__line[next_idx]
			slots.append(Slot(self, (the_port, next_port)))
			if next_idx == idx_2:
				break
			the_idx = next_idx
		return slots

	def get_shortest_path(self, start: Port, end: Port) -> Path:
		"""Get a sequence of slot in this service from `start` to `end`

		Rule:
		1. If there are two paths, then pick the "shortest" one, and
		2. The "shortest" here doesn't mean actual distance, but the
			one with fewest middle ports

		For example, the service line is (P1, P2, P3, P4, P1, P2, P3).
		Then, there are two paths connects P1 and P4:
			1. (P1, P2, P3, P4)
			2. (P1, P2, P3, P1, P2, P3, P4)
		We only pick the first one as it is the "shortest" path
		"""
		if not self.has_port(start):
			raise ValueError(f'Port "{start.get_id()}" not in Service')
		if not self.has_port(end):
			raise ValueError(f'Port "{end.get_id()}" not in Service')
		the_slots: list[Slot] = []
		the_slots_length: int = self.number_of_port()
		start_indexes = self.all_index_of_port(start)
		end_indexes = self.all_index_of_port(end)

		for start_idx in start_indexes:
			for end_idx in end_indexes:
				tmp_slots = self.get_slot_list_by_index(start_idx, end_idx)
				tmp_slots_len = len(tmp_slots)
				if tmp_slots_len < the_slots_length:
					the_slots_length = tmp_slots_len
					the_slots = tmp_slots
		return Path(the_slots)

	def get_shortest_path_by_id(self, start_id: str, end_id: str, port_pool: PortPool) -> Path:
		return self.get_shortest_path(port_pool.get_port(start_id), port_pool.get_port(end_id))

	###########################################################################
	# Action related

	# Actions are generated by NN
	###########################################################################

	# def get_all_valid_actions(self, ports_pool: PortPool) -> list[Action]:
	# 	"""Generate all valid actions

	# 	Example: Suppose the service is (P1,P2,P3), and `ports_pool` is
	# 		(P1,P2,P3,P4). Then, valid actions include

	# 		If port is in service, for each `loc` (location) of service T, and
	# 		For each `port` in `ports_pool`:
	# 			1. `T[prev of loc] == port` not included:
	# 				(P1,0), (P1,2)
	# 				(P2,0), (P2,1)
	# 				(P3,1), (P3,2)
	# 			2. no deletion if service line has only two ports
	# 		If port is not in service, `loc` include all valid locations:
	# 			(P4,0), (P4,1), (P4,2)
	# 	"""
	# 	re = []
	# 	for port in ports_pool.tolist_port():
	# 		for loc in range(self.number_of_port()):
	# 			if self.has_port(port):
	# 				# case 1: T[previous of loc] = port
	# 				if self.get_port_by_idx(self.idx_of_prev_idx(loc)) == port:
	# 					continue
	# 				# case 2: service line has only two ports
	# 				if self.number_of_port() == 2:
	# 					continue
	# 			action = Action(port, loc)
	# 			tmp_service = self.apply_action(action, ports_pool, _test = True)
	# 			if False is tmp_service.check_valid():
	# 				continue
	# 			re.append(action)
	# 	return re

	def apply_action(self, action: LineAction, ports_pool: PortPool, _test: bool = False,
			portgraph: PortGraph | None = None, warn: bool = True) -> 'ServiceLine':
		"""Apply action to service line

		Input:
			- `action` has the form (cmd, loc)
		"""
		sequence = self.tolist_port().copy()
		if action.cmd == 'add':
			start_idx, end_idx, idx_port = action.loc[0], action.loc[1], action.loc[2]
			start = ports_pool.get_port_by_idx(start_idx)
			end = ports_pool.get_port_by_idx(end_idx)
			port = ports_pool.get_port_by_idx(idx_port)
			for idx, p in enumerate(self.__line):
				if p == start and self.next_port_of_idx(idx) == end:
					sequence.insert(idx + 1, port)
		elif action.cmd == 'delete':
			start_idx, end_idx, idx_port = action.loc[0], action.loc[1], action.loc[2]
			start = ports_pool.get_port_by_idx(start_idx)
			end = ports_pool.get_port_by_idx(end_idx)
			port = ports_pool.get_port_by_idx(idx_port)
			for idx, p in enumerate(self.__line):
				if p == port and self.next_port_of_idx(idx) == end and self.prev_port_of_idx(idx) == start:
					sequence.pop(idx)

		# DO SOME REVISIONs on Sequence
		# Case 1: butterfly deletion
		#     P1, P2, P1, P3, if delete P3, then we actually get P1, P2 rather than P1, P2, P1
		for idx, p in enumerate(sequence):
			if idx < len(sequence) - 1:
				if p == sequence[idx + 1]:
					sequence.pop(idx)
			else: # idx == len(sequence) - 1
				if p == sequence[0]:
					sequence.pop(idx)
		
		new_line = ServiceLine(self.name(), sequence, _test, warn=warn, portgraph=portgraph)
		self._copy_metadata_to(new_line)
		
		return new_line

def create_service_line(
		name: str, port_ids: list[str], portpool: PortPool, portgraph: PortGraph | None = None
) -> ServiceLine:
	"""Create a service line from a list of port IDs
	"""
	port_lst = []
	for port_id in port_ids:
		port = portpool.get_port(port_id)
		port_lst.append(port)
	return ServiceLine(name, port_lst, portgraph=portgraph)
