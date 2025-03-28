import chardet
from typing import Tuple
from importlib import resources

from .vessel import Vessel, VesselPool
from .port import Port, PortPool, PortGraph
from .serviceline import ServiceLine

import pandas as pd
import numpy as np


data_file_vessel = "data_2024-12-23/VESSEL_CLASS_Dataset.xlsx"
data_file_port = "data_2024-12-23/Port_Dataset.xlsx"
data_file_port_call = "data_2024-12-23/PORT_CALL_Details_Dataset.xlsx"
data_file_sail_distance = "data_2024-12-23/SAILING_DISTANCE_Dataset.csv"
data_file_demand = "data_2024-12-23/Demand_Dataset.xlsx"
data_file_current_line = "data_2024-12-23/CURR_LINES_Dataset.xlsx"

def read_vessel_class_data() -> VesselPool:
	file = resources.files('cma.res').joinpath(data_file_vessel)
	df = pd.read_excel(file)  # read first table
	df = df.rename(columns=lambda x: x.strip())  # trim titles
	vessels_list = []
	numbers_list = []

	for _, row in df.iterrows():
		vessel = Vessel(
			row['VC Rank'],
			row['Vessel Class'],
			row['Max Capacity (TEU)'],
			row['Min Draft (m)'],
			row['Ave Chartering Cost (Daily)'],
			[
				{ 'speed': 10, 'consumption': row['10KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 11, 'consumption': row['11KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 12, 'consumption': row['12KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 13, 'consumption': row['13KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 14, 'consumption': row['14KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 15, 'consumption': row['15KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 16, 'consumption': row['16KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 17, 'consumption': row['17KTS Bunkering Consumption (mtons/day)'] },
				{ 'speed': 18, 'consumption': row['18KTS Bunkering Consumption (mtons/day)'] },
			],
			row['Bunker price per mtons']
			)
		vessel_number = row['Number of vessels by class']
		vessels_list.append(vessel)
		numbers_list.append(vessel_number)
	return VesselPool(vessels_list, numbers_list)

def read_port_data() -> Tuple[PortPool, PortPool]:
	"""
	return:
	- A larger pool of ports with some data not complete
	- Pool of ports whose data are more compete
	"""
	port_pool = PortPool()
	port_pool_list_complete_info = []
	# 1. port data
	#
	file1 = resources.files('cma.res').joinpath(data_file_port)
	df_port = pd.read_excel(file1)
	df_port = df_port.rename(columns=lambda x: x.strip())  # trim titles
	for _, row in df_port.iterrows():
		# deal with transshipment cost dummy:
		transshipment_cost = row['Transhipment Cost']
		if transshipment_cost == 5000:
			transshipment_cost = 0
		# deal with storage cost dummy:
		storage_cost = row['Storage Cost']
		if storage_cost == 1000000:
			storage_cost = 0
		port_pool.add_port(
			row['Port ID'],  # port ID
			row['Port ID'],  # port name
			row['Longitude'],
			row['Latitude'],
			{},  # fit vessels
			[],  # port call cost
			[],  # berth productivity
			transshipment_cost,
			storage_cost,
			row['Transhipment Capacity'],
			row['Max Draft'],
			row['Max Daily Port Call'],
			2,  # max number of visit in a line
		)
	# 2. port call data (filter)
	#
	file2 = resources.files('cma.res').joinpath(data_file_port_call)
	df_port_call_1 = pd.read_excel(file2, sheet_name = 'Sheet1')  # read first table
	df_port_call_2 = pd.read_excel(file2, sheet_name = 'Sheet2')  # read first table
	df_port_call_1 = df_port_call_1.rename(columns=lambda x: x.strip())  # trim titles
	df_port_call_2 = df_port_call_2.rename(columns=lambda x: x.strip())  # trim titles

	# read sheet 1 data
	for _, row in df_port_call_1.iterrows():
		port_id = row['Port Code']
		try:
			port = port_pool.get_port(port_id)
		except:
			continue
		distinct_vessel_count = row['Distinct Vessel Count']
		if np.isnan(distinct_vessel_count):
			distinct_vessel_count = 99999
		port.fit_vessel_ranks[row['VC_Rank']] = int(distinct_vessel_count)
		port.cost_call.append(row['Ave Port Call Cost'])
		port.berth_productivity.append(row['Gross Berth Productivity (mph)_avg'])
		if port not in port_pool_list_complete_info:
			port_pool_list_complete_info.append(port)
	# read sheet 2 data
	for _, row in df_port_call_2.iterrows():
		port_id = row['Port Code']
		try:
			port = port_pool.get_port(port_id)
		except:
			continue
		if port in port_pool_list_complete_info:
			if row['VC_Rank'] not in port.fit_vessel_ranks:
				port.fit_vessel_ranks[row['VC_Rank']] = 99999
				port.cost_call.append(row['Ave Port Call Cost'])

	return port_pool, PortPool(port_pool_list_complete_info)

def read_sailing_distance_data(portpool: PortPool) -> np.matrix:
	"""input `portpool` to determine the size of distance matrix
	"""
	port_mapping = {
		p.get_id() : idx for idx, p in enumerate(portpool.tolist_port())
	}
	dist_matrix = np.ones((len(port_mapping), len(port_mapping))) * float('inf')
	file = resources.files('cma.res').joinpath(data_file_sail_distance)
	df = pd.read_csv(str(file))  # read first table
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

def read_demand_data(portpool: PortPool) -> tuple[dict, np.matrix]:
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

def read_current_line_data(portpool: PortPool, display = False) -> tuple[list[ServiceLine], list[int]]:
	"""input `portpool` as a filter
	return:
	- current lines
	- weeks
	"""
	current_lines = []
	current_lines_weeks = []

	file = resources.files('cma.res').joinpath(data_file_current_line)
	df = pd.read_excel(file, sheet_name='Sheet1')  # read first table
	df = df.rename(columns=lambda x: x.strip())  # trim titles

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
		total_weeks = (np.sum(sailing_days) + np.sum(staying_days)) / 7.0
		try:
			line = ServiceLine(line_name, port_id_list, portpool, display=display)
		except:
			continue
		current_lines.append(line)
		current_lines_weeks.append(int(np.round(total_weeks)))
	return current_lines, current_lines_weeks

def analysis_weeks(portgraph: PortGraph):
	"""Predict how many weeks to complete the route

	input: `portpool` as a filter
	"""
	current_lines, current_lines_weeks = read_current_line_data(portgraph)
	current_lines_id = []
	current_lines_sailing_distance = []
	current_lines_stops_number = []
	for line in current_lines:
		current_lines_id.append(line.name())
		sailing_distance = line.get_distance(portgraph)
		current_lines_sailing_distance.append(sailing_distance)
		current_lines_stops_number.append(line.number_of_port())

	df = pd.DataFrame({
		'id': current_lines_id,
		'weeks': current_lines_weeks,
		'sailing_distance': current_lines_sailing_distance,
		'stops_number': current_lines_stops_number
	})
	return current_lines, df
