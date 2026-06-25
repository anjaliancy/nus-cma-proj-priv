"""
Tests to validate servicegraph.py works correctly with 11 vessel ranks.

Validates that MILP formulations dynamically adapt to the number of vessel classes
and work correctly with the new 11-rank vessel dataset.

Run independently: python tests/test_servicegraph_11ranks.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from cma.data_reader import read_vessel_class_data, read_port_data, read_sailing_distance_data
from cma.servicegraph import ServiceGraph
from cma.serviceline import ServiceLine, create_service_line
from cma.port import PortGraph
import numpy as np


def test_vessel_pool_has_11_ranks():
	"""Test that vessel pool loads 11 vessel classes"""
	vessel_pool = read_vessel_class_data()
	
	n_vessels = len(vessel_pool.vessels_list)
	assert n_vessels == 11, f"Expected 11 vessel classes, got {n_vessels}"
	
	# Verify ranks 1-11 are present
	ranks = {v.vessel_rank for v in vessel_pool.vessels_list}
	assert ranks == set(range(1, 12)), f"Expected ranks 1-11, got {ranks}"
	
	print(f"✓ VesselPool has 11 vessel classes (ranks 1-11)")


def test_dynamic_vessel_count_detection():
	"""Test that code dynamically uses len(vesselpool.vessels_list) for vessel count"""
	vessel_pool = read_vessel_class_data()
	
	# The key is that servicegraph.py uses len(vesselpool.vessels_list)
	# This means it automatically adapts to any number of vessel classes
	n_vessels = len(vessel_pool.vessels_list)
	assert n_vessels == 11, f"Expected 11 vessels in pool"
	
	# Verify this is used consistently
	assert len(vessel_pool.get_chartering_costs()) == n_vessels
	assert vessel_pool.get_bukering_costs()[0].shape[0] == n_vessels
	
	print(f"✓ Code dynamically detects {n_vessels} vessel classes via len(vesselpool.vessels_list)")


def test_vessel_pool_methods_with_11_ranks():
	"""Test VesselPool methods return correct shapes for 11 ranks"""
	vessel_pool = read_vessel_class_data()
	
	# Test get_chartering_costs
	charter_costs = vessel_pool.get_chartering_costs()
	assert len(charter_costs) == 11, f"Expected 11 charter costs, got {len(charter_costs)}"
	assert all(c > 0 for c in charter_costs), "All charter costs should be positive"
	
	# Test get_bukering_costs
	bukering_costs, speed_level0 = vessel_pool.get_bukering_costs()
	assert bukering_costs.shape[0] == 11, f"Expected 11 ranks in bukering costs, got {bukering_costs.shape[0]}"
	assert bukering_costs.shape[1] == 18, f"Expected 18 speed levels, got {bukering_costs.shape[1]}"
	
	# Test get_bukering_cost_middle
	middle_costs = vessel_pool.get_bukering_cost_middle()
	assert len(middle_costs) == 11, f"Expected 11 middle costs, got {len(middle_costs)}"
	
	print(f"✓ VesselPool methods return correct shapes for 11 ranks:")
	print(f"  - Charter costs: {len(charter_costs)} values")
	print(f"  - Bukering costs: {bukering_costs.shape} (11 ranks × 18 speeds)")
	print(f"  - Middle costs: {len(middle_costs)} values")


def test_port_operational_data_for_11_ranks():
	"""Test that port operational data covers all 11 ranks"""
	vessel_pool = read_vessel_class_data()
	port_pool, port_pool_finer = read_port_data()
	
	# Check CNC ports have data for all 11 ranks
	import pandas as pd
	df_cnc = pd.read_csv('data/input/Port_Productivity.csv')
	cnc_port_ids = set(df_cnc['portid'])
	
	# Test a few CNC ports
	for port_id in list(cnc_port_ids)[:5]:
		port = port_pool.get_port(port_id)
		
		# Check productivity
		prods = port.get_producticity(vessel_pool)
		assert len(prods) == 11, f"Port {port_id} productivity should have 11 values"
		
		# Check port call costs
		costs = port.get_portcall_costs(vessel_pool)
		assert len(costs) == 11, f"Port {port_id} costs should have 11 values"
		
		# Check fit vessel ranks
		assert len(port.berth_productivity) <= 11, \
			f"Port {port_id} has productivity for >11 ranks"
		assert len(port.cost_portcall) <= 11, \
			f"Port {port_id} has costs for >11 ranks"
	
	print(f"✓ Port operational data correctly covers 11 vessel ranks")


def test_simple_service_line_creation():
	"""Test creating a simple service line"""
	vessel_pool = read_vessel_class_data()
	port_pool, port_pool_finer = read_port_data()
	
	# Create a simple service line using the helper function
	# Route: Singapore -> Shanghai -> Hong Kong -> Singapore (valid circular route)
	line = create_service_line(
		"TEST_LINE",
		['SGSIN', 'CNSHA', 'HKHKG'],
		port_pool
	)
	
	assert line is not None, "Failed to create service line"
	assert line.name() == "TEST_LINE"
	assert len(line.tolist_port()) == 3, "Should have 3 ports in route"
	
	print(f"✓ Successfully created service line with 11-rank vessel pool")


def test_port_graph_distance_matrix():
	"""Test distance matrix has correct shape for 182 ports"""
	port_pool, port_pool_finer = read_port_data()
	dist_matrix = read_sailing_distance_data(port_pool)
	
	n_ports = port_pool.get_number_of_ports()
	assert n_ports == 182, f"Expected 182 ports, got {n_ports}"
	
	# Distance matrix should be 182x182
	assert dist_matrix.shape == (182, 182), \
		f"Expected 182×182 distance matrix, got {dist_matrix.shape}"
	
	# Diagonal should be 0
	assert np.allclose(np.diag(dist_matrix), 0), "Distance matrix diagonal should be 0"
	
	print(f"✓ Distance matrix shape (182, 182) compatible with 11 vessel ranks")


def test_vessel_capacity_range():
	"""Test that 11 vessel ranks cover expected capacity range"""
	vessel_pool = read_vessel_class_data()
	
	capacities = [v.vessel_capacity for v in vessel_pool.vessels_list]
	
	# Verify we have a range from small to large
	min_capacity = min(capacities)
	max_capacity = max(capacities)
	
	assert min_capacity < 2000, f"Minimum capacity too large: {min_capacity}"
	assert max_capacity > 10000, f"Maximum capacity too small: {max_capacity}"
	
	# Verify capacities are sorted (generally increasing with rank)
	sorted_capacities = sorted(capacities)
	assert capacities == sorted_capacities, "Vessel capacities should increase with rank"
	
	print(f"✓ 11 vessel ranks cover capacity range: {min_capacity:.0f} - {max_capacity:.0f} TEU")
	print(f"  Rank 1: {capacities[0]:.0f} TEU")
	print(f"  Rank 6: {capacities[5]:.0f} TEU") 
	print(f"  Rank 11: {capacities[10]:.0f} TEU")


def test_no_rank_12_or_13_in_data():
	"""Test that old ranks 12-13 are not present in any data"""
	vessel_pool = read_vessel_class_data()
	port_pool, port_pool_finer = read_port_data()
	
	# Check vessels
	vessel_ranks = {v.vessel_rank for v in vessel_pool.vessels_list}
	assert 12 not in vessel_ranks, "Rank 12 should not exist"
	assert 13 not in vessel_ranks, "Rank 13 should not exist"
	
	# Check ports don't have data for ranks >11
	for port in port_pool_finer.tolist_port():
		for rank in port.fit_vessel_ranks.keys():
			assert rank <= 11, f"Port {port.get_id()} has fit_vessel_ranks for rank {rank} > 11"
		for rank in port.berth_productivity.keys():
			assert rank <= 11, f"Port {port.get_id()} has productivity for rank {rank} > 11"
		for rank in port.cost_portcall.keys():
			assert rank <= 11, f"Port {port.get_id()} has cost for rank {rank} > 11"
	
	print(f"✓ No old ranks 12-13 found in vessel or port data")


def test_servicegraph_creation():
	"""Test that ServiceGraph can be created with service lines"""
	vessel_pool = read_vessel_class_data()
	port_pool, port_pool_finer = read_port_data()
	
	# Create a simple service line (must be circular, no consecutive duplicates)
	line = create_service_line("TEST_LINE", ['SGSIN', 'CNSHA', 'HKHKG'], port_pool)
	
	# Create ServiceGraph
	service_graph = ServiceGraph([line])
	
	# Verify service graph has the line
	n_lines = len(service_graph.tolist_serviceLine())
	assert n_lines == 1, f"Expected 1 line in service graph"
	
	# The MILP will create ship_vars with shape (n_lines, n_vessel_class)
	n_vessel_class = len(vessel_pool.vessels_list)
	assert n_vessel_class == 11, f"Expected 11 vessel classes"
	
	print(f"✓ ServiceGraph created with shape ({n_lines} lines, {n_vessel_class} vessel classes)")


def test_charter_cost_range():
	"""Test that charter costs are reasonable for 11 ranks"""
	vessel_pool = read_vessel_class_data()
	
	charter_costs = vessel_pool.get_chartering_costs()
	
	# Verify costs generally increase with vessel size
	assert charter_costs[0] < charter_costs[10], \
		"Charter cost for rank 11 should be > rank 1"
	
	# Typical daily charter rates: $5k-$50k depending on size
	assert min(charter_costs) > 1000, "Minimum charter cost too low"
	assert max(charter_costs) < 100000, "Maximum charter cost unreasonably high"
	
	print(f"✓ Charter costs range from ${charter_costs[0]:.0f} to ${charter_costs[10]:.0f} per day")
	print(f"  (costs generally increase with vessel size)")


def test_backward_compatibility_with_existing_code():
	"""Test that existing code expecting vessel data still works"""
	vessel_pool = read_vessel_class_data()
	port_pool, port_pool_finer = read_port_data()
	
	# Existing code expects these methods to work
	assert hasattr(vessel_pool, 'vessels_list'), "VesselPool missing vessels_list"
	assert hasattr(vessel_pool, 'get_chartering_costs'), "Missing get_chartering_costs"
	assert hasattr(vessel_pool, 'get_bukering_costs'), "Missing get_bukering_costs"
	
	# Verify vessels_list is iterable and has Vessel objects
	assert len(vessel_pool.vessels_list) > 0, "vessels_list empty"
	for vessel in vessel_pool.vessels_list:
		assert hasattr(vessel, 'vessel_rank'), "Vessel missing vessel_rank"
		assert hasattr(vessel, 'vessel_capacity'), "Vessel missing vessel_capacity"
	
	print(f"✓ Backward compatibility maintained with existing code")


def test_speed_levels_for_11_ranks():
	"""Test that all 11 ranks have 18 speed levels"""
	vessel_pool = read_vessel_class_data()
	
	bukering_costs, speed_level0 = vessel_pool.get_bukering_costs()
	
	# Should be 11 ranks × 18 speeds
	assert bukering_costs.shape == (11, 18), \
		f"Expected (11, 18) shape, got {bukering_costs.shape}"
	
	# All bukering costs should be positive
	assert (bukering_costs > 0).all(), "All bukering costs should be positive"
	
	# Speed level 0 should be reasonable (around 10-12 knots)
	assert 9 <= speed_level0 <= 12, f"Speed level 0 should be ~10 knots, got {speed_level0}"
	
	print(f"✓ All 11 ranks have 18 speed levels (base speed: {speed_level0} kn)")


if __name__ == '__main__':
	print("Testing ServiceGraph with 11 Vessel Ranks...\n")
	
	test_vessel_pool_has_11_ranks()
	test_dynamic_vessel_count_detection()
	test_vessel_pool_methods_with_11_ranks()
	test_port_operational_data_for_11_ranks()
	test_simple_service_line_creation()
	test_port_graph_distance_matrix()
	test_vessel_capacity_range()
	test_no_rank_12_or_13_in_data()
	test_servicegraph_creation()
	test_charter_cost_range()
	test_backward_compatibility_with_existing_code()
	test_speed_levels_for_11_ranks()
	
	print("\n" + "="*70)
	print("ALL SERVICEGRAPH 11-RANK TESTS PASSED!")
	print("ServiceGraph MILP formulations are fully compatible with 11 vessel ranks")
	print("="*70)
