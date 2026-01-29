from typing import Tuple
from importlib import resources
import random

from .vessel import Vessel, VesselPool
from .port import Port, PortPool, PortGraph
from .serviceline import ServiceLine

import pandas as pd
import numpy as np


# Configuration constants
BUNKER_PRICE = 579.0  # USD per metric ton (default from legacy data)
DEFAULT_VESSEL_DRAFT = 15.0  # meters (default when not specified)

data_file_vessel = "input/Vessel_Nominal.csv"
data_file_port = "input/Port_Dataset.csv"
data_file_port_call = "data_2024-12-23/PORT_CALL_Details_Dataset.xlsx"
data_file_sail_distance = "data_2024-12-23/SAILING_DISTANCE_Dataset.csv"
data_file_demand = "data_2024-12-23/Demand_Dataset.xlsx"

# CNC enhanced port operation files (56 ports with detailed operational data)
data_file_port_productivity = "input/Port_Productivity.csv"
data_file_portcall_costs = "input/Portcall_Costs.csv"
data_file_port_waiting = "input/Port_WaitingTimes.csv"
data_file_port_maneuvering = "input/Port_ManTimes.csv"
data_file_port_apac = "data_2024-12-23/port_APAC.csv"

# CNC demand data with transit time expectations
data_file_demand_cnc = "input/demand_CNC_adjusted_comp.csv"

# CNC proforma service lines (34 service lines with operational details)
data_file_proforma = "input/proforma_CNC.csv"
data_file_current_line = "data_2024-12-23/CURR_LINES_Dataset.xlsx"

def read_vessel_class_data() -> VesselPool:
	"""Read vessel class data from CNC input/Vessel_Nominal.csv
	
	Returns VesselPool with 11 vessel ranks (1-11) with enhanced fuel consumption curves.
	New data features:
	- 18 speed levels from 10.0 to 18.5 knots (0.5 knot increments)
	- Operational fuel components: canal, port, maneuvering, sea (available in CSV)
	
	Note: Unlimited fleet size (fleet availability not constrained)
	"""
	file = resources.files('cma.res').joinpath(data_file_vessel)
	df = pd.read_csv(file)
	df = df.rename(columns=lambda x: x.strip())  # trim titles
	vessels_list = []
	numbers_list = []

	# Speed levels in new data: 10.0, 10.5, 11.0, ..., 18.0, 18.5 (18 levels)
	speed_columns = [f'cons_{speed}kn' for speed in 
					 [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5, 
					  14.0, 14.5, 15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5]]
	
	for _, row in df.iterrows():
		# Parse size class string (e.g., "100 - 499") to tuple
		size_class_str = row['sizeclass']
		if ' - ' in size_class_str:
			parts = size_class_str.split(' - ')
			size_class = (int(parts[0]), int(parts[1]))
		else:
			# Fallback for unexpected format
			size_class = size_class_str
		
		# Build consumption list with 18 speed levels
		bunkering_cost_coefs = []
		for idx, col in enumerate(speed_columns):
			speed = 10.0 + (idx * 0.5)  # 10.0, 10.5, 11.0, ..., 18.5
			consumption = row[col]
			bunkering_cost_coefs.append({
				'speed': speed,
				'consumption': consumption
			})
		
		vessel = Vessel(
			int(row['vrank']),
			size_class,
			float(row['cap_nom']),
			DEFAULT_VESSEL_DRAFT,  # Not specified in new data, use default
			float(row['cost_charter']),
			bunkering_cost_coefs,
			BUNKER_PRICE
		)
		
		# Note: Operational fuel components available in CSV but not stored in Vessel object
		# due to __slots__ constraint. Can be added to Vessel class in future if needed:
		# - cons_canal: float(row['cons_canal'])
		# - cons_port: float(row['cons_port']) 
		# - cons_man: float(row['cons_man'])
		# - cons_sea: float(row['cons_sea'])
		
		# Unlimited fleet (no vessel count constraint in new data)
		vessel_number = 99999  # Effectively unlimited
		
		vessels_list.append(vessel)
		numbers_list.append(vessel_number)
	
	return VesselPool(vessels_list, numbers_list)

def read_port_data() -> Tuple[PortPool, PortPool]:
	"""Read port data from hybrid sources: CNC CSV files + legacy Excel fallback
	
	Strategy:
	- Basic port data (182 ports): input/Port_Dataset.csv
	- Operational data (56 CNC ports): input/Port_Productivity.csv, Portcall_Costs.csv, 
	  Port_WaitingTimes.csv, Port_ManTimes.csv
	- Operational data (~126 non-CNC ports): data_2024-12-23/PORT_CALL_Details_Dataset.xlsx
	
	Returns:
	- `port_pool`: A larger pool of ports with some data not complete
	- `port_pool_finer`: A pool of ports whose data are more complete, with
		- fit vessel ranks and numbers
		- portcall cost for each vessel
		- berth productivity
		- waiting times (CNC ports only)
		- maneuvering times (CNC ports only)
	"""
	port_pool = PortPool()
	
	# Step 0: Load APAC port subset (Far East and Oceania)
	file_apac = resources.files('cma.res').joinpath(data_file_port_apac)
	df_apac = pd.read_csv(file_apac)
	df_apac['Region'] = df_apac['Region'].astype(str)
	apac_port_ids = set(df_apac[df_apac['Region'].str.contains('FAR EAST|OCEANIA', na=False)]['Port_Code'])

	# Step 1: Load basic port data from CSV (all 182 ports)
	file_basic = resources.files('cma.res').joinpath(data_file_port)
	df_port = pd.read_csv(file_basic)
	df_port = df_port.rename(columns=lambda x: x.strip())
	
	for _, row in df_port.iterrows():
		port_id = row['PortID']
		# Skip non-APAC ports
		if port_id not in apac_port_ids:
			continue

		# Handle dummy values
		transshipment_cost = row['TranshipmentCost']
		if transshipment_cost == 5000:
			transshipment_cost = 0
		storage_cost = row['StorageCost']
		if storage_cost == 1000000:
			storage_cost = 0
		
		port_pool.add_port(
			row['PortID'],
			row['PortID'],
			row['Longitude'],
			row['Latitude'],
			{},  # fit vessels - filled later
			{},  # berth productivity - filled later
			{},  # port call cost - filled later
			transshipment_cost,
			storage_cost,
			row['TranshipmentCapacity'],
			row['MaxDraft'],
			row['MaxDailyPortCall']
		)
	
	# Step 2: Load CNC enhanced operational data (56 ports, 11 vessel ranks)
	file_productivity = resources.files('cma.res').joinpath(data_file_port_productivity)
	file_costs = resources.files('cma.res').joinpath(data_file_portcall_costs)
	file_waiting = resources.files('cma.res').joinpath(data_file_port_waiting)
	file_maneuvering = resources.files('cma.res').joinpath(data_file_port_maneuvering)
	
	df_productivity = pd.read_csv(file_productivity)
	df_costs = pd.read_csv(file_costs)
	df_waiting = pd.read_csv(file_waiting)
	df_maneuvering = pd.read_csv(file_maneuvering)
	
	port_pool_finer = []
	cnc_ports_processed = set()
	
	# Process CNC ports - each row is a port, columns 1-11 are vessel ranks
	for _, row in df_productivity.iterrows():
		port_id = row['portid']
		try:
			port = port_pool.get_port(port_id)
		except:
			continue  # Port not in basic dataset
		
		# Load productivity for ranks 1-11
		for rank in range(1, 12):
			productivity = row[str(rank)]
			if not np.isnan(productivity):
				port.berth_productivity[rank] = productivity
		
		# Load port call costs for ranks 1-11
		cost_row = df_costs[df_costs['portid'] == port_id].iloc[0]
		for rank in range(1, 12):
			cost = cost_row[str(rank)]
			if not np.isnan(cost):
				port.cost_portcall[rank] = cost
		
		# Load waiting times for ranks 1-11
		waiting_row = df_waiting[df_waiting['portid'] == port_id].iloc[0]
		waiting_times = {}
		for rank in range(1, 12):
			waiting = waiting_row[str(rank)]
			if not np.isnan(waiting):
				waiting_times[rank] = waiting
		port.waiting_time = waiting_times  # Add as new attribute
		
		# Load maneuvering times (in/out, not rank-specific)
		man_row = df_maneuvering[df_maneuvering['portid'] == port_id].iloc[0]
		port.maneuvering_time_in = man_row['manin']
		port.maneuvering_time_out = man_row['manout']
		
		# Set fit vessel ranks (CNC ports can handle all 11 ranks, unlimited capacity)
		for rank in range(1, 12):
			port.fit_vessel_ranks[rank] = 99999
		
		port_pool_finer.append(port)
		cnc_ports_processed.add(port_id)
	
	# Step 3: Load legacy operational data for non-CNC ports (~126 ports)
	file_legacy = resources.files('cma.res').joinpath(data_file_port_call)
	df_legacy_1 = pd.read_excel(file_legacy, sheet_name='Sheet1')
	df_legacy_2 = pd.read_excel(file_legacy, sheet_name='Sheet2')
	df_legacy_1 = df_legacy_1.rename(columns=lambda x: x.strip())
	df_legacy_2 = df_legacy_2.rename(columns=lambda x: x.strip())
	
	# Process Sheet1 (main operational data)
	for _, row in df_legacy_1.iterrows():
		port_id = row['Port Code']
		
		# Skip if already processed as CNC port
		if port_id in cnc_ports_processed:
			continue
		
		try:
			port = port_pool.get_port(port_id)
		except:
			continue
		
		# Note: Legacy data uses VC_Rank which may be 1-13, but we only have 1-11 now
		# Only process ranks 1-11 to match new vessel dataset
		vc_rank = row['VC_Rank']
		if vc_rank > 11:
			continue  # Skip old vessel ranks 12-13
		
		distinct_vessel_count = row['Distinct Vessel Count']
		if np.isnan(distinct_vessel_count):
			distinct_vessel_count = 99999
		
		port.fit_vessel_ranks[vc_rank] = distinct_vessel_count
		port.cost_portcall[vc_rank] = row['Ave Port Call Cost']
		port.berth_productivity[vc_rank] = row['Gross Berth Productivity (mph)_avg']
		
		if port not in port_pool_finer:
			port_pool_finer.append(port)
	
	# Process Sheet2 (supplemental operational data)
	for _, row in df_legacy_2.iterrows():
		port_id = row['Port Code']
		
		# Skip if already processed as CNC port
		if port_id in cnc_ports_processed:
			continue
		
		try:
			port = port_pool.get_port(port_id)
		except:
			continue
		
		if port not in port_pool_finer:
			continue  # Only update ports already in finer pool
		
		vc_rank = row['VC_Rank']
		if vc_rank > 11:
			continue  # Skip old vessel ranks 12-13
		
		port.fit_vessel_ranks[vc_rank] = 99999
		if isinstance(row['Ave Port Call Cost'], float):
			port.cost_portcall[vc_rank] = row['Ave Port Call Cost']
	
	return port_pool, PortPool(port_pool_finer)

def read_sailing_distance_data(portpool: PortPool) -> np.ndarray:
	"""input `portpool` to determine the size of distance matrix
	"""
	port_mapping = {
		p.get_id() : idx for idx, p in enumerate(portpool.tolist_port())
	}
	dist_matrix = np.ones((len(port_mapping), len(port_mapping))) * float('inf')
	file = resources.files('cma.res').joinpath(data_file_sail_distance)
	df = pd.read_csv(str(file), low_memory=False)  # read first table
	df = df.rename(columns=lambda x: x.strip())  # trim titles

	for _, row in df.iterrows():
		from_port = port_mapping.get(row['Port Departure'], -1)
		to_port = port_mapping.get(row['Port Arrival'], -1)
		dist = row['Sailing Distance (Nautical miles)']
		if from_port >= 0 and to_port >= 0:
			dist_matrix[from_port, to_port] = dist
		# else:
		#     print(row)
	np.fill_diagonal(dist_matrix, 0)
	return np.matrix(dist_matrix)

def read_demand_data(portpool: PortPool) -> tuple[dict, np.ndarray]:
	"""
	Input:
		`portpool` to determine the size of demand matrix
	Return:
		a list of 7 demand matrices from Monday to Sunday, and the total demand
	"""
	port_mapping = {
		p.get_id() : idx for idx, p in enumerate(portpool.tolist_port())
	}
	days = ["Mon", "Tues", "Wed", "Thurs", "Fri", "Sat", "Sun"]
	demands = [np.ones((len(port_mapping), len(port_mapping))) * 0.0 for _ in range(7)]
	total_demands = np.ones((len(port_mapping), len(port_mapping))) * 0.0
	demands_dict = dict(zip(days, demands))

	file = resources.files('cma.res').joinpath(data_file_demand)
	df = pd.read_excel(file, sheet_name="Sheet1")
	df = df.rename(columns=lambda x: x.strip())  # trim titles

	for _, row in df.iterrows():
		from_port = port_mapping.get(row['LOAD_PORT'], -1)
		to_port = port_mapping.get(row['DISCHARGE_PORT'], -1)
		departure_day = row['DEPARTURE_DAY']
		weekly_TEUs = row['TEUS']

		if from_port >= 0 and to_port >= 0:
			demand_mat = demands_dict[departure_day]
			demand_mat[from_port, to_port] += weekly_TEUs
		# else:
		#     print(row)
	for key in demands_dict:
		demand_day = demands_dict[key]
		total_demands += demand_day
	return demands_dict, np.matrix(total_demands)

def read_demand_with_transit_time(portpool: PortPool) -> tuple[np.ndarray, np.ndarray]:
	"""Read CNC demand data with expected transit times
	
	Input:
		`portpool` to determine the size of demand matrix
	
	Return:
		tuple of (demand_matrix, transit_time_matrix)
		- demand_matrix: Weekly demand in TEUs for each OD pair
		- transit_time_matrix: Expected transit time in days for each OD pair
		
	Note: Multiple rows for same OD pair are aggregated:
		- Demand: summed across all rows
		- Transit time: weighted average by demand volume
	"""
	n_ports = len(portpool.tolist_port())
	port_mapping = {p.get_id(): idx for idx, p in enumerate(portpool.tolist_port())}
	
	demand_matrix = np.zeros((n_ports, n_ports))
	transit_time_matrix = np.zeros((n_ports, n_ports))
	transit_time_weights = np.zeros((n_ports, n_ports))  # Track weights for averaging
	
	file = resources.files('cma.res').joinpath(data_file_demand_cnc)
	df = pd.read_csv(file)
	df = df.rename(columns=lambda x: x.strip())
	
	for _, row in df.iterrows():
		pol_pod = row['POL_POD']
		pol, pod = pol_pod.split('-')
		
		from_idx = port_mapping.get(pol, -1)
		to_idx = port_mapping.get(pod, -1)
		
		if from_idx >= 0 and to_idx >= 0:
			teus = row['TEUS']
			td_exp = row['TD_Exp']  # Expected transit days
			th_exp = row['TH_Exp']  # Expected transit hours
			transit_days = td_exp + th_exp / 24.0  # Convert to total days
			
			# Accumulate demand
			demand_matrix[from_idx, to_idx] += teus
			
			# Weighted average for transit time (by demand volume)
			transit_time_weights[from_idx, to_idx] += teus
			transit_time_matrix[from_idx, to_idx] += transit_days * teus
	
	# Compute weighted average transit time
	# Avoid division by zero for pairs with no demand
	mask = transit_time_weights > 0
	transit_time_matrix[mask] /= transit_time_weights[mask]
	
	return np.matrix(demand_matrix), np.matrix(transit_time_matrix)

def read_current_line_data(portpool: PortPool,
		verbose=False, warn=True
	) -> tuple[list[ServiceLine], list[int]]:
	"""input `portpool` as a filter
	return:
	- current lines
	- weeks
	"""
	current_lines = []
	current_lines_weeks = []

	file = resources.files('cma.res').joinpath(data_file_current_line)
	df = pd.read_excel(file, sheet_name='Sheet1')  # read first table
	df = df.rename(columns=lambda x: x.strip())    # trim titles

	df_grouped = df.groupby('Line Name').agg({
		'Port ID': list,
		'Port Call Day': list,
		'Time to next port (in day)': list,
		'Stay time at port (in day)': list
	}).reset_index()

	for _, row in df_grouped.iterrows():
		line_name = row['Line Name']
		port_id_list = row['Port ID']
		sailing_days = row['Time to next port (in day)']
		staying_days = row['Stay time at port (in day)']
		total_weeks = int(np.round((np.sum(sailing_days) + np.sum(staying_days)) / 7.0))
		try:
			port_list = [portpool.get_port(port_id) for port_id in port_id_list]
			line = ServiceLine(line_name, port_list, verbose=verbose, warn=warn)
		except:
			continue
		line.week = total_weeks
		current_lines.append(line)
		current_lines_weeks.append(total_weeks)
	return current_lines, current_lines_weeks

def read_cnc_proforma_data(portpool: PortPool, vesselpool: VesselPool) -> dict:
	"""Read CNC proforma service lines from input/proforma_CNC.csv
	
	Returns a dictionary with:
	- 'lines': List of 34 ServiceLine objects representing CNC proforma routes
	- 'metadata': Dictionary of line metadata (vessel rank, speed, capacity, etc.)
	
	The proforma data contains actual CNC service line operations with:
	- Port rotations (sequence of port calls)
	- Vessel assignments (rank, nominal capacity)
	- Operational details (speed, waiting time, stay time, maneuvering time)
	- Capacity allocation and utilization
	
	This data can be used for:
	- Validation: Compare optimized solutions against actual CNC operations
	- Benchmarking: Assess optimization improvements over current operations
	- Analysis: Understand CNC service line patterns and constraints
	"""
	file = resources.files('cma.res').joinpath(data_file_proforma)
	df = pd.read_csv(file)
	df = df.rename(columns=lambda x: x.strip())
	
	# Group by line name to get all port calls per line
	lines = []
	metadata = {}
	
	line_names = df['linename'].unique()
	
	for line_name in line_names:
		df_line = df[df['linename'] == line_name].sort_values('sequence')
		
		# Extract port rotation
		port_ids = df_line['portid'].tolist()
		
		# Try to create service line with port list
		try:
			port_list = [portpool.get_port(port_id) for port_id in port_ids]
			line = ServiceLine(line_name, port_list, verbose=False, warn=False)
			lines.append(line)
			
			# Store metadata for this line
			first_row = df_line.iloc[0]
			metadata[line_name] = {
				'vessel_rank': int(first_row['vrank']),
				'vessel_capacity_nominal': first_row['cap_nom'],
				'vessel_capacity_effective': first_row['cap_eff'],
				'speed': first_row['vspeed'],  
				'ignore_buffer_lb': bool(first_row.get('ignore_buffer_lb', 0)),
				'port_calls': len(port_ids),
				'port_rotation': port_ids,
				'total_duration': df_line['duration'].sum(),
				'total_moves': df_line['moves'].sum(),
				'service_type': first_row['svc_type'],
				# Detailed operational data per port
				'port_details': []
			}
			
			# Add per-port operational details
			for _, row in df_line.iterrows():
				metadata[line_name]['port_details'].append({
					'port_id': row['portid'],
					'sequence': int(row['sequence']),
					'waiting_time': row['time_wait'],
					'maneuvering_in': row['time_manin'],
					'stay_time': row['staytime'],
					'maneuvering_out': row['time_manout'],
					'time_to_next': row['timetonext'],
					'speed_to_next': row['vspeed'],
					'moves': row['moves'],
					'productivity': row['ops_prod'],
					'allocation': row['alloc'],
					'capacity_scale': row['cap_scale'],
					'capacity_reserve': row['cap_reserve'],
					'ignore_buffer_lb': bool(row.get('ignore_buffer_lb', metadata[line_name]['ignore_buffer_lb']))
				})

			# Attach buffer-related profile to the service line for later use in optimization
			waiting_times = [d['waiting_time'] for d in metadata[line_name]['port_details']]
			speeds_to_next = [d['speed_to_next'] for d in metadata[line_name]['port_details']]
			ignore_lb_flag = metadata[line_name]['ignore_buffer_lb']
			if hasattr(line, 'set_buffer_profile'):
				line.set_buffer_profile(waiting_times, speeds_to_next, ignore_lb_flag)
			
		except Exception as e:
			# Some ports might not be in portpool, skip those lines
			# some lines are not valid
			continue
	
	return {
		'lines': lines,
		'metadata': metadata
	}

def randomly_create_lines(
		portpool: PortPool,
		line_num: int
	) -> list[ServiceLine]:
	"""
	Randomly create a service graph without reading any data
	"""
	current_lines = []
	port_num = portpool.get_number_of_ports()
	print(port_num)

	for idx_line in range(line_num):
		line_name = f'line_{idx_line + 1}'
		idx_o = random.randint(0, port_num - 1)
		idx_d = random.randint(0, port_num - 1)
		if idx_o == idx_d:
			idx_d += 1
			idx_d %= (port_num - 1)
		port_o = portpool.get_port_by_idx(idx_o)
		port_d = portpool.get_port_by_idx(idx_d)
		line = ServiceLine(
			line_name, [port_o, port_d]
		)
		current_lines.append(line)
	return current_lines

