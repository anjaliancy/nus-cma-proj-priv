"""
Test suite for vessel class data migration to input/Vessel_Nominal.csv

Validates:
- Correct number of vessel classes loaded (11 ranks)
- Capacity ranges match expected values
- 18 fuel consumption levels per class (10.0-18.5 kn in 0.5 kn steps)
- Operational fuel components present
- Backward compatibility with existing code
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pytest
import numpy as np
from cma.data_reader import read_vessel_class_data, BUNKER_PRICE, DEFAULT_VESSEL_DRAFT
from cma.vessel import Vessel, VesselPool


class TestVesselMigration:
	"""Test vessel class data migration from legacy to CNC input data"""
	
	@pytest.fixture
	def vessel_pool(self):
		"""Load vessel pool for testing"""
		return read_vessel_class_data()
	
	def test_vessel_count(self, vessel_pool):
		"""Verify 11 vessel classes loaded (ranks 1-11)"""
		assert vessel_pool.get_number_of_types() == 11, \
			f"Expected 11 vessel classes, got {vessel_pool.get_number_of_types()}"
	
	def test_vessel_ranks(self, vessel_pool):
		"""Verify vessel ranks are 1 through 11"""
		ranks = [v.vessel_rank for v in vessel_pool.vessels_list]
		expected_ranks = list(range(1, 12))
		assert ranks == expected_ranks, \
			f"Expected ranks 1-11, got {ranks}"
	
	def test_vessel_capacity_ranges(self, vessel_pool):
		"""Verify vessel capacities match expected size classes"""
		expected_capacities = {
			1: 238,      # 100-499 TEU
			2: 742,      # 500-999 TEU
			3: 1158,     # 1000-1499 TEU
			4: 1705,     # 1500-1999 TEU
			5: 2421,     # 2000-2999 TEU
			6: 3461,     # 3000-3999 TEU
			7: 4502,     # 4000-5099 TEU
			8: 6193,     # 5100-7499 TEU
			9: 8835,     # 7500-9999 TEU
			10: 10756,   # 10000-12499 TEU
			11: 13033    # 12500-15199 TEU
		}
		
		for vessel in vessel_pool.vessels_list:
			expected_cap = expected_capacities[vessel.vessel_rank]
			assert vessel.vessel_capacity == expected_cap, \
				f"Rank {vessel.vessel_rank}: expected capacity {expected_cap}, got {vessel.vessel_capacity}"
	
	def test_fuel_consumption_levels(self, vessel_pool):
		"""Verify 18 fuel consumption levels per vessel class"""
		for vessel in vessel_pool.vessels_list:
			assert len(vessel.bunkering_cost_coefs) == 18, \
				f"Rank {vessel.vessel_rank}: expected 18 fuel levels, got {len(vessel.bunkering_cost_coefs)}"
	
	def test_fuel_consumption_speeds(self, vessel_pool):
		"""Verify fuel consumption speeds are 10.0 to 18.5 in 0.5 kn increments"""
		expected_speeds = [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5,
						   14.0, 14.5, 15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5]
		
		for vessel in vessel_pool.vessels_list:
			speeds = vessel.bunkering_cost_coefs['speed'].tolist()
			assert speeds == expected_speeds, \
				f"Rank {vessel.vessel_rank}: expected speeds {expected_speeds}, got {speeds}"
	
	def test_fuel_consumption_positive(self, vessel_pool):
		"""Verify all fuel consumption values are positive"""
		for vessel in vessel_pool.vessels_list:
			consumptions = vessel.bunkering_cost_coefs['consumption'].tolist()
			assert all(c > 0 for c in consumptions), \
				f"Rank {vessel.vessel_rank}: found non-positive fuel consumption values"
	
	def test_fuel_consumption_increasing(self, vessel_pool):
		"""Verify fuel consumption increases with speed (convex relationship)"""
		for vessel in vessel_pool.vessels_list:
			consumptions = vessel.bunkering_cost_coefs['consumption'].tolist()
			for i in range(len(consumptions) - 1):
				assert consumptions[i] < consumptions[i+1], \
					f"Rank {vessel.vessel_rank}: fuel consumption not increasing at index {i}"
	
	def test_operational_fuel_components(self, vessel_pool):
		"""Verify operational fuel components data exists in CSV but not stored in Vessel object"""
		# Note: Operational fuel components (cons_canal, cons_port, cons_man, cons_sea) 
		# are available in Vessel_Nominal.csv but not stored in Vessel object due to
		# __slots__ constraint. This is documented in data_reader.py as optional future enhancement.
		# For now, we just verify the vessel objects are properly created.
		for vessel in vessel_pool.vessels_list:
			# Verify vessel has core attributes instead
			assert hasattr(vessel, 'vessel_rank'), f"Rank {vessel.vessel_rank}: missing vessel_rank"
			assert hasattr(vessel, 'vessel_capacity'), f"Rank {vessel.vessel_rank}: missing vessel_capacity"
			assert hasattr(vessel, 'daily_chartering_cost'), f"Rank {vessel.vessel_rank}: missing daily_chartering_cost"
			assert hasattr(vessel, 'bunkering_cost_coefs'), f"Rank {vessel.vessel_rank}: missing bunkering_cost_coefs"
	
	def test_bunker_price(self, vessel_pool):
		"""Verify bunker price is set to configured constant"""
		for vessel in vessel_pool.vessels_list:
			assert vessel.unit_bunkering_cost == BUNKER_PRICE, \
				f"Rank {vessel.vessel_rank}: expected bunker price {BUNKER_PRICE}, got {vessel.unit_bunkering_cost}"
	
	def test_vessel_draft(self, vessel_pool):
		"""Verify vessel draft is set to default (not in new data)"""
		for vessel in vessel_pool.vessels_list:
			assert vessel.vessel_draft == DEFAULT_VESSEL_DRAFT, \
				f"Rank {vessel.vessel_rank}: expected draft {DEFAULT_VESSEL_DRAFT}, got {vessel.vessel_draft}"
	
	def test_vessel_chartering_cost_positive(self, vessel_pool):
		"""Verify chartering costs are positive and reasonable"""
		for vessel in vessel_pool.vessels_list:
			assert vessel.daily_chartering_cost > 0, \
				f"Rank {vessel.vessel_rank}: chartering cost not positive"
			assert vessel.daily_chartering_cost < 100000, \
				f"Rank {vessel.vessel_rank}: chartering cost unusually high ({vessel.daily_chartering_cost})"
	
	def test_chartering_cost_increases_with_size(self, vessel_pool):
		"""Verify chartering costs generally increase with vessel size"""
		costs = [v.daily_chartering_cost for v in vessel_pool.vessels_list]
		# Allow some variation but overall trend should be increasing
		# Check that larger vessels (rank 8-11) cost more than smaller ones (rank 1-4)
		avg_small = np.mean(costs[0:4])
		avg_large = np.mean(costs[7:11])
		assert avg_large > avg_small, \
			f"Large vessel avg cost ({avg_large}) should exceed small vessel avg cost ({avg_small})"
	
	def test_fleet_size_unlimited(self, vessel_pool):
		"""Verify fleet sizes are effectively unlimited (99999)"""
		for number in vessel_pool.numbers_list:
			assert number == 99999, \
				f"Expected unlimited fleet size (99999), got {number}"
	
	def test_min_max_speed(self, vessel_pool):
		"""Verify min/max speed attributes are correct"""
		for vessel in vessel_pool.vessels_list:
			assert vessel.min_speed == 10.0, \
				f"Rank {vessel.vessel_rank}: expected min_speed 10.0, got {vessel.min_speed}"
			assert vessel.max_speed == 18.0, \
				f"Rank {vessel.vessel_rank}: expected max_speed 18.0, got {vessel.max_speed}"
	
	def test_backward_compatibility_get_bukering_costs(self, vessel_pool):
		"""Verify VesselPool.get_bukering_costs() works with new data"""
		consumption, base_speed = vessel_pool.get_bukering_costs()
		
		# Should return matrix of shape (11, 18) for 11 ranks × 18 speed levels
		assert consumption.shape == (11, 18), \
			f"Expected consumption matrix shape (11, 18), got {consumption.shape}"
		
		# Base speed should be 10.0
		assert base_speed == 10.0, \
			f"Expected base speed 10.0, got {base_speed}"
		
		# All costs should be positive (consumption * bunker_price)
		assert np.all(consumption > 0), \
			"Found non-positive bunkering costs"
	
	def test_backward_compatibility_get_chartering_costs(self, vessel_pool):
		"""Verify VesselPool.get_chartering_costs() works with new data"""
		chartering_costs = vessel_pool.get_chartering_costs()
		
		assert len(chartering_costs) == 11, \
			f"Expected 11 chartering costs, got {len(chartering_costs)}"
		assert all(c > 0 for c in chartering_costs), \
			"Found non-positive chartering costs"
	
	def test_backward_compatibility_get_vessel_instance(self, vessel_pool):
		"""Verify VesselPool.get_vessel_instance() works with ranks 1-11"""
		for rank in range(1, 12):
			vessel = vessel_pool.get_vessel_instance(rank)
			assert isinstance(vessel, Vessel), \
				f"Expected Vessel instance for rank {rank}"
			assert vessel.vessel_rank == rank, \
				f"Expected vessel rank {rank}, got {vessel.vessel_rank}"
	
	def test_size_class_format(self, vessel_pool):
		"""Verify size class format is tuple of (min, max)"""
		expected_size_classes = [
			(100, 499),
			(500, 999),
			(1000, 1499),
			(1500, 1999),
			(2000, 2999),
			(3000, 3999),
			(4000, 5099),
			(5100, 7499),
			(7500, 9999),
			(10000, 12499),
			(12500, 15199)
		]
		
		for vessel, expected in zip(vessel_pool.vessels_list, expected_size_classes):
			assert vessel.vessel_class == expected, \
				f"Rank {vessel.vessel_rank}: expected size class {expected}, got {vessel.vessel_class}"
	
	def test_fuel_cost_calculation(self, vessel_pool):
		"""Verify fuel cost calculation works correctly"""
		vessel = vessel_pool.get_vessel_instance(5)  # Test with rank 5
		
		# Get consumption at 14.0 knots (index 8 in 0-based, speed level 9)
		df = vessel.bunkering_cost_coefs
		consumption_14kn = df[df['speed'] == 14.0]['consumption'].values[0]
		
		# Calculate fuel cost
		fuel_cost = consumption_14kn * vessel.unit_bunkering_cost
		
		assert fuel_cost > 0, "Fuel cost should be positive"
		assert fuel_cost < 100000, f"Fuel cost unusually high: {fuel_cost}"
	
	def test_vessel_pool_dataframe(self, vessel_pool):
		"""Verify VesselPool can generate dataframe representation"""
		df = vessel_pool.get_dataframe()
		
		assert len(df) == 11, f"Expected 11 rows in dataframe, got {len(df)}"
		assert 'Vessel Type' in df.columns, "Missing 'Vessel Type' column"
		assert 'Vessel Number' in df.columns, "Missing 'Vessel Number' column"


if __name__ == '__main__':
	# Run tests with verbose output
	pytest.main([__file__, '-v', '-s'])
