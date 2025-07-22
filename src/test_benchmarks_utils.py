import pandas as pd
import numpy as np
from pprint import pprint

from cma import Vessel, VesselPool
from cma import Port, PortPool, PortGraph
from cma import ServiceLine

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

# def read_demand(portpool: PortPool) -> tuple[dict, np.ndarray]:
# 	"""
# 	"""
# 	all_source = set(df_demand['Origin'].values)
# 	all_dest = set(df_demand['Destination'].values)
# 	all_ports_id = list(all_source.union(all_dest))
# 	port_lst = []
# 	for p_id in all_ports_id:
# 		if portpool.has_port_by_id(p_id):
# 			pass


def read_port_data(cma_portpool: PortPool) -> PortPool:
	"""
	"""
	all_source = set(df_demand['Origin'].values)
	all_dest = set(df_demand['Destination'].values)
	all_ports_id = all_source.union(all_dest)
	# pprint(len(all_ports_id))
	# pprint(all_ports_id)
	port_lst = []

	for p_id in all_ports_id:
		if cma_portpool.has_port_by_id(p_id):
			port = cma_portpool.get_port(p_id)
			port_lst.append(port)

	portpool = PortPool(port_lst)
	return portpool

