import pandas as pd
import numpy as np

from cma import Vessel, VesselPool
from cma import Port, PortPool
from cma import ServiceGraph
from cma import create_service_line
from cma import read_port_data as cma_read_port_data

df_demand = pd.read_csv('data/benchmarks/LINERLIB/data/Demand_Pacific.csv', sep='\t')
df_vessel = pd.read_csv('data/benchmarks/LINERLIB/data/fleet_data.csv', sep='\t')
df_vessel_num = pd.read_csv('data/benchmarks/LINERLIB/data/fleet_Pacific.csv', sep='\t')
df_ports = pd.read_csv('data/benchmarks/LINERLIB/data/ports.csv', sep='\t')
df_demand = pd.read_csv('data/benchmarks/LINERLIB/data/Demand_Pacific.csv', sep='\t')


def read_vessel_class_data() -> VesselPool:
	"""
	"""
	vessel_lst = []
	number_lst = []
	idx_row = 1
	for _, row in df_vessel.iterrows():
		# vessel list
		vessel = Vessel(
			idx_row,
			row['Vessel class'],
			row['Capacity FFE'],
			row['draft'],
			row['TC rate daily (fixed Cost)'],  # daily chartering cost
			[{
				'speed': row['designSpeed'],
				'consumption': row['Bunker ton per day at designSpeed'],
			}],
			600  # unit bunkering cost by the data
		)
		vessel.idle_bunkering_cost = row['Idle Consumption ton/day']
		vessel.min_speed = row['minSpeed']
		vessel.max_speed = row['maxSpeed']
		vessel_lst.append(vessel)
		idx_row += 1

		# number list
		if vessel.vessel_class in df_vessel_num['Vessel class'].values:
			idx_row_dfnum = df_vessel_num['Vessel class'] == vessel.vessel_class
			vessel_num = df_vessel_num.loc[idx_row_dfnum, 'Quantity']
			number_lst.append(vessel_num.values[0])
		else:
			number_lst.append(0)

	return VesselPool(vessel_lst, number_lst)


def read_demand(portpool: PortPool):
	"""
	"""
	port_mapping = {
		p.get_id() : idx for idx, p in enumerate(portpool.tolist_port())
	}
	week_demands = np.ones((len(port_mapping), len(port_mapping))) * 0.0
	unit_revenue = np.ones((len(port_mapping), len(port_mapping))) * 0.0
	#mat_IsPanama = np.ones((len(port_mapping), len(port_mapping))) * 0
	#mat_IsSuez = np.ones((len(port_mapping), len(port_mapping))) * 0

	for _, row in df_demand.iterrows():
		from_port = port_mapping.get(row['Origin'], -1)
		to_port = port_mapping.get(row['Destination'], -1)
		week_amount = row['FFEPerWeek']
		revenue_per_unit = row['Revenue_1']
		#is_Panama = row['IsPanama']
		#is_Suez = row['IsSuez']
		if from_port >= 0 and to_port >= 0:
			week_demands[from_port, to_port] += week_amount
			unit_revenue[from_port, to_port] += revenue_per_unit
			# if is_Panama > 0:
			# 	mat_IsPanama[from_port, to_port] = 1
			# if is_Suez > 0:
			# 	mat_IsSuez[from_port, to_port] = 1
	return week_demands, unit_revenue #, mat_IsPanama, mat_IsSuez


def read_port_data(vesselpool: VesselPool, cma_portpool: PortPool) -> PortPool:
	"""
	"""
	# all_source = set(df_demand['Origin'].values)
	# all_dest = set(df_demand['Destination'].values)
	all_ports_id = df_ports['UNLocode'].values
	port_lst = []

	for p_id in all_ports_id:
		#if cma_portpool.has_port_by_id(p_id):
		#	port = cma_portpool.get_port(p_id)
		#	port.transshipment_capacity = True
		#	port_lst.append(port)
		#else:
			row = df_ports.loc[df_ports['UNLocode'] == p_id].iloc[0]
			port = Port(
				port_id=p_id,
				name=row['name'],
				longitude=row['Longitude'],
				latitude=row['Latitude'],
				fit_vessel_ranks={
					1: 99,
					2: 99,
					3: 99,
					4: 99,
					5: 99,
					6: 99
				},
				berth_productivity={
					1: 35,
					2: 35,
					3: 35,
					4: 35,
					5: 35,
					6: 35
				},
				cost_portcall={
		1: row['PortCallCostFixed']
			+ vesselpool.get_vessel_instance(1).vessel_capacity * row['PortCallCostPerFFE'],
		2: row['PortCallCostFixed']
			+ vesselpool.get_vessel_instance(2).vessel_capacity * row['PortCallCostPerFFE'],
		3: row['PortCallCostFixed']
			+ vesselpool.get_vessel_instance(3).vessel_capacity * row['PortCallCostPerFFE'],
		4: row['PortCallCostFixed']
			+ vesselpool.get_vessel_instance(4).vessel_capacity * row['PortCallCostPerFFE'],
		5: row['PortCallCostFixed']
			+ vesselpool.get_vessel_instance(5).vessel_capacity * row['PortCallCostPerFFE'],
		6: row['PortCallCostFixed']
			+ vesselpool.get_vessel_instance(6).vessel_capacity * row['PortCallCostPerFFE'],
				},
				cost_transship=row['CostPerFULLTrnsf'],
				cost_storage=0,
				transshipment_capacity=row['CostPerFULLTrnsf'] is not None,
				max_draft=row['Draft'],
				max_daily_call=99,
				max_line_visit=99
			)
			port_lst.append(port)
	portpool = PortPool(port_lst)
	return portpool


line_1_idlst = ['CNXMN', 'KRPUS', 'TWKHH', 'PHMNL', 'CNYTN', 'HKHKG',
	'VNHPH', 'IDSUB', 'MYPEN', 'MYPKG', 'SGSIN', 'MYTPP', 'THLCH']
line_2_idlst = ['SGSIN', 'CNFOC', 'CNTAO', 'CNDLC', 'CAVAN', 'USSEA', 'CNXMN',
	'KRPUS', 'USOAK', 'MXLZC', 'USLAX', 'HKHKG', 'CNYTN', 'MYTPP']
line_3_idlst = ['MYTPP', 'CNSHA', 'JPYOK', 'PABLB']
line_4_idlst = ['CNDLC', 'CNXMN', 'MYTPP', 'CNTAO']
line_5_idlst = ['KRPUS', 'HKHKG', 'TWKHH', 'JPNGO', 'JPYOK', 'USLAX', 'CNTAO', 'PABLB']
line_6_idlst = ['USOAK', 'JPYOK', 'TWKHH', 'CNSHA', 'CNTAO', 'CNDLC', 'USLGB', 'USLAX']
line_7_idlst = ['SGSIN', 'HKHKG', 'KRPUS', 'USOAK', 'USLAX', 'JPYOK', 'TWKHH', 'MYTPP']
line_8_idlst = ['VNDAD', 'MYTPP', 'THLCH', 'MYTPP', 'IDSRG', 'IDJKT', 'VNSGN']
line_9_idlst = ['SGSIN', 'THLCH', 'MYTPP', 'VNSGN']
line_10_idlst = ['TWKHH', 'MYTPP', 'MYPKG', 'CNYTN']
line_11_idlst = ['NICIO', 'MXLZC', 'PAMIT', 'PABLB', 'SVAQJ']
line_12_idlst = ['MXESE', 'HKHKG', 'CNSHA', 'KRPUS', 'USOAK', 'SVAQJ', 'PABLB']
line_13_idlst = ['JPTYO', 'JPYOK', 'JPHKT', 'KRPUS']
line_14_idlst = ['SGSIN', 'MYTPP', 'CNYTN', 'CNTAO', 'KRPUS', 'CNLYG', 'JPSMZ', 'JPYOK', 'JPUKB', 'CNSHA', 'TWKHH']
line_15_idlst = ['CNDLC', 'JPYOK', 'JPUKB', 'KRPUS', 'CNTAO', 'HKHKG', 'MYTPP', 'CNYTN']
line_16_idlst = ['CNYTN', 'TWKHH', 'PHGES', 'CNSHA', 'IDJKT', 'THLCH', 'MYTPP', 'SGSIN', 'VNSGN']
line_17_idlst = ['TWKEL', 'CNYTN']




