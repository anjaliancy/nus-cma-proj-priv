import pandas as pd
from cma import Vessel, VesselPool
from cma import Port, PortPool, PortGraph
from cma import ServiceLine

df_demand = pd.read_csv('./LINERLIB/data/Demand_Pacific.csv', sep='\t')
df_vessel = pd.read_csv('./LINERLIB/data/fleet_Data.csv', sep='\t')

def read_vessel_class_data() -> VesselPool:
	"""
	"""
	for idx_row, row in df_vessel.iterrows():
		vessel = Vessel(
			idx_row + 1,
			row['Vessel class'],
			row['Capacity FFE'],
			row['draft'],
			row['TC rate daily (fixed Cost)'],  # daily chartering cost
			None,
			row['Bunker ton per day at designSpeed']
		)
