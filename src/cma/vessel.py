"""
Module `vessel`

Define all vessel related classes and methods
"""

import pandas as pd
import numpy as np
from typing import Tuple

################################################################################
# Vessel ralated
################################################################################

class Vessel:
	"""class Vessel

	The ships that transfer goods
	"""
	__slots__ = [
		'vessel_rank',				# int
		'vessel_class',				# Tuple[int, int]
		'vessel_capacity',			# float
		'vessel_draft',				# float
		'daily_chartering_cost',	# float
		'bunkering_cost_coefs',		# pd.DataFrame
		'idle_bunkering_cost',		# float
		'unit_bunkering_cost',		# float
		'min_speed',				# float
		'max_speed',				# float
	]

	def __init__(self,
			v_rank: int,               # from 1 to 13
			v_class: Tuple[int, int],  # `100 - 499`
			capacity: float,
			draft: float,
			daily_chartering_cost: float,
			bunkering_cost_coefs: list[dict],  # List[{'speed': int, 'consumption': float}]
			unit_bunkering_cost: float
	):
		self.vessel_rank = v_rank
		self.vessel_class = v_class
		self.vessel_capacity = capacity
		self.vessel_draft = draft
		self.daily_chartering_cost = daily_chartering_cost
		self.bunkering_cost_coefs = pd.DataFrame(bunkering_cost_coefs)
		self.idle_bunkering_cost = 0.0
		self.unit_bunkering_cost = unit_bunkering_cost
		self.min_speed = 10  # cma data
		self.max_speed = 18  # cma data

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

	def get_bukering_costs(self) -> tuple[np.ndarray, int]:
		"""
		A list of bukering costs of all speed for each vessel class
		"""
		n_vessel_ranks = len(self.vessels_list)
		n_speed_levels = len(self.vessels_list[0].bunkering_cost_coefs)
		base_speed_level = self.vessels_list[0].bunkering_cost_coefs.at[0, 'speed']
		consumption = np.ones(shape=(n_vessel_ranks, n_speed_levels))
		for vessel in self.vessels_list:
			df = vessel.bunkering_cost_coefs
			consumption[vessel.vessel_rank - 1, :] = df['consumption'] * vessel.unit_bunkering_cost
		return consumption, base_speed_level

	def get_bukering_cost_middle(self) -> list[float]:
		"""
		A list of bukering cost for each vessel class at the middle speed
		"""
		re = []
		for vessel in self.vessels_list:
			df = vessel.bunkering_cost_coefs
			df_nrow = df.shape[0]
			cost = df.at[df_nrow // 2, 'consumption'] * vessel.unit_bunkering_cost
			re.append(cost)
		return re

	def get_bunkering_cost_idle(self) -> list[float]:
		"""
		A list of bukering cost for each vessel class staying at port (ton/day)
		"""
		re = []
		for vessel in self.vessels_list:
			re.append(vessel.idle_bunkering_cost * vessel.unit_bunkering_cost)
		return re

	def get_chartering_costs(self) -> list[float]:
		"""
		Return: a list of daily chartering cost for each vessel class
		"""
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

	def get_speed_levels(self) -> np.ndarray:
		"""
		Return the speed levels (kts) available in the bunkering cost data
		"""
		if not self.vessels_list:
			return np.array([])
		return self.vessels_list[0].bunkering_cost_coefs['speed'].values
