"""
Module `vessel`

Define all vessel related classes and methods
"""

import pandas as pd
from typing import Tuple

################################################################################
# Vessel ralated
################################################################################

class Vessel:
	"""class Vessel

	The ships that transfer goods
	"""
	vessel_rank: int
	vessel_class: Tuple[int, int]
	vessel_capacity: float
	vessel_draft: float
	daily_chartering_cost: float
	bunkering_cost_coefs: list[dict]
	unit_bunkering_cost: float

	def __init__(self, v_rank, v_class, capacity, draft,
				daily_chartering_cost, bunkering_cost_coefs, unit_bunkering_cost):
		self.vessel_rank = v_rank
		self.vessel_class = v_class
		self.vessel_capacity = capacity
		self.vessel_draft = draft
		self.daily_chartering_cost = daily_chartering_cost
		self.bunkering_cost_coefs = bunkering_cost_coefs
		self.unit_bunkering_cost = unit_bunkering_cost

	def __repr__(self) -> str:
		return 'Rank ' + str(self.vessel_rank) + ' Vessel'

class VesselPool:
	"""class VesselPool

	The collection of all vessel resources
	"""
	vessels_list: list[Vessel]
	numbers_list: list[int]

	def __init__(self, vessels_list, numbers_list):
		self.vessels_list = vessels_list
		self.numbers_list = numbers_list

	def __repr__(self) -> str:
		return str(self.get_dataframe())

	def get_dataframe(self) -> pd.DataFrame:
		return pd.DataFrame({
			'Vessel Type' : self.vessels_list,
			'Vessel Number' : self.numbers_list
		})

	def get_bukering_cost_middle(self) -> list[float]:
		re = []
		for vessel in self.vessels_list:
			cost_coef = vessel.bunkering_cost_coefs[5]['consumption']
			cost = cost_coef * vessel.unit_bunkering_cost
			re.append(cost)
		return re

	def get_chartering_costs(self) -> list[float]:
		c_costs = []
		for vessel in self.vessels_list:
			c_costs.append(vessel.daily_chartering_cost)
		return c_costs

	def get_vessel_instance(self, v_rank: int) -> Vessel:
		"""
		input: v_rank from 1 to 13
		"""
		return self.vessels_list[v_rank - 1]

	def get_number_of_types(self) -> int:
		return len(self.vessels_list)
