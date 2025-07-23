import pandas as pd
import numpy as np

from cma import Vessel, VesselPool
from cma import Port, PortPool


df_demand = pd.read_csv('./LINERLIB/data/Demand_Pacific.csv', sep='\t')
df_vessel = pd.read_csv('./LINERLIB/data/fleet_Data.csv', sep='\t')
df_vessel_num = pd.read_csv('./LINERLIB/data/fleet_Pacific.csv', sep='\t')
df_ports = pd.read_csv('./LINERLIB/data/ports.csv', sep='\t')
df_demand = pd.read_csv('./LINERLIB/data/Demand_Pacific.csv', sep='\t')


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
			579  # unit bunkering cost is set the same as CMA data
		)
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


def read_demand(portpool: PortPool) -> tuple[np.ndarray, np.ndarray]:
	"""
	"""
	port_mapping = {
		p.get_id() : idx for idx, p in enumerate(portpool.tolist_port())
	}
	week_demands = np.ones((len(port_mapping), len(port_mapping))) * 0.0
	unit_revenue = np.ones((len(port_mapping), len(port_mapping))) * 0.0

	for _, row in df_demand.iterrows():
		from_port = port_mapping.get(row['Origin'], -1)
		to_port = port_mapping.get(row['Destination'], -1)
		week_amount = row['FFEPerWeek']
		revenue_per_unit = row['Revenue_1'] / week_amount
		if from_port >= 0 and to_port >= 0:
			week_demands[from_port, to_port] += week_amount
			unit_revenue[from_port, to_port] += revenue_per_unit
	return week_demands, unit_revenue


def read_port_data(vesselpool: VesselPool, cma_portpool: PortPool) -> PortPool:
	"""
	"""
	all_source = set(df_demand['Origin'].values)
	all_dest = set(df_demand['Destination'].values)
	all_ports_id = all_source.union(all_dest)
	port_lst = []

	for p_id in all_ports_id:
		if cma_portpool.has_port_by_id(p_id):
			port = cma_portpool.get_port(p_id)
			port_lst.append(port)
		else:
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
				transshipment_capacity=True,
				max_draft=row['Draft'],
				max_daily_call=99,
				max_line_visit=2
			)
			port_lst.append(port)
	portpool = PortPool(port_lst)
	return portpool

