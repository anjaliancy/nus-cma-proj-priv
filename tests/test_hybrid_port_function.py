"""
Function-level tests for hybrid read_port_data() implementation.

Tests the dual-source port data loading:
- 182 ports from input/Port_Dataset.csv
- 56 CNC ports with enhanced operational data from 4 CSV files
- ~126 non-CNC ports with legacy operational data from Excel

Run independently: python tests/test_hybrid_port_function.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from cma.data_reader import read_port_data
import pandas as pd


def test_port_pools_loaded():
	"""Test that both port pools are returned and non-empty"""
	port_pool, port_pool_finer = read_port_data()
	
	assert port_pool is not None, "port_pool is None"
	assert port_pool_finer is not None, "port_pool_finer is None"
	
	assert port_pool.get_number_of_ports() > 0, "port_pool is empty"
	assert port_pool_finer.get_number_of_ports() > 0, "port_pool_finer is empty"
	
	print(f"✓ Both port pools loaded: {port_pool.get_number_of_ports()} total, "
	      f"{port_pool_finer.get_number_of_ports()} with operational data")


def test_all_182_ports_in_main_pool():
	"""Test that all 182 ports from CSV are in main port pool"""
	port_pool, _ = read_port_data()
	
	# Load reference CSV
	df = pd.read_csv('src/cma/res/input/Port_Dataset.csv')
	expected_count = len(df)
	
	actual_count = port_pool.get_number_of_ports()
	assert actual_count == expected_count, \
		f"Expected {expected_count} ports, got {actual_count}"
	
	# Check all CSV port IDs are in pool
	for port_id in df['PortID']:
		port = port_pool.get_port(port_id)
		assert port is not None, f"Port {port_id} not found in pool"
		assert port.get_id() == port_id, f"Port ID mismatch: {port.get_id()} != {port_id}"
	
	print(f"✓ All {expected_count} ports from CSV loaded into main pool")


def test_cnc_ports_in_finer_pool():
	"""Test that CNC ports (56) are in finer pool with enhanced data"""
	port_pool, port_pool_finer = read_port_data()
	
	# Load CNC port IDs
	df_cnc = pd.read_csv('src/cma/res/input/Port_Productivity.csv')
	cnc_port_ids = set(df_cnc['portid'])
	
	# Check all CNC ports are in finer pool
	finer_ports = {p.get_id() for p in port_pool_finer.tolist_port()}
	cnc_in_finer = cnc_port_ids & finer_ports
	
	assert len(cnc_in_finer) == 56, \
		f"Expected 56 CNC ports in finer pool, found {len(cnc_in_finer)}"
	
	missing_cnc = cnc_port_ids - finer_ports
	assert len(missing_cnc) == 0, f"CNC ports missing from finer pool: {missing_cnc}"
	
	print(f"✓ All 56 CNC ports in finer pool with enhanced operational data")


def test_cnc_ports_have_11_ranks():
	"""Test that CNC ports have operational data for all 11 vessel ranks"""
	port_pool, port_pool_finer = read_port_data()
	
	# Load CNC port IDs
	df_cnc = pd.read_csv('src/cma/res/input/Port_Productivity.csv')
	cnc_port_ids = set(df_cnc['portid'])
	
	# Check each CNC port has data for ranks 1-11
	for port_id in cnc_port_ids:
		port = port_pool.get_port(port_id)
		
		# Check all ranks 1-11 present
		for rank in range(1, 12):
			assert rank in port.fit_vessel_ranks, \
				f"CNC port {port_id} missing fit_vessel_ranks for rank {rank}"
			assert rank in port.berth_productivity, \
				f"CNC port {port_id} missing berth_productivity for rank {rank}"
			assert rank in port.cost_portcall, \
				f"CNC port {port_id} missing cost_portcall for rank {rank}"
		
		# Verify fit_vessel_ranks is 99999 (unlimited)
		assert port.fit_vessel_ranks[1] == 99999, \
			f"CNC port {port_id} fit_vessel_ranks not unlimited"
	
	print(f"✓ All 56 CNC ports have operational data for ranks 1-11")


def test_cnc_ports_have_waiting_and_maneuvering():
	"""Test that CNC ports have waiting and maneuvering time attributes"""
	port_pool, _ = read_port_data()
	
	# Load CNC port IDs
	df_cnc = pd.read_csv('src/cma/res/input/Port_Productivity.csv')
	cnc_port_ids = set(df_cnc['portid'])
	
	for port_id in cnc_port_ids:
		port = port_pool.get_port(port_id)
		
		# Check waiting_time attribute exists and has 11 ranks
		assert hasattr(port, 'waiting_time'), \
			f"CNC port {port_id} missing waiting_time attribute"
		assert isinstance(port.waiting_time, dict), \
			f"CNC port {port_id} waiting_time not a dict"
		assert len(port.waiting_time) == 11, \
			f"CNC port {port_id} waiting_time doesn't have 11 ranks"
		
		# Check maneuvering time attributes exist
		assert hasattr(port, 'maneuvering_time_in'), \
			f"CNC port {port_id} missing maneuvering_time_in"
		assert hasattr(port, 'maneuvering_time_out'), \
			f"CNC port {port_id} missing maneuvering_time_out"
		
		# Verify values are positive
		assert port.maneuvering_time_in > 0, \
			f"CNC port {port_id} maneuvering_time_in not positive"
		assert port.maneuvering_time_out > 0, \
			f"CNC port {port_id} maneuvering_time_out not positive"
	
	print(f"✓ All 56 CNC ports have waiting_time dict (11 ranks) and maneuvering times")


def test_legacy_ports_in_finer_pool():
	"""Test that legacy (non-CNC) ports are also in finer pool"""
	port_pool, port_pool_finer = read_port_data()
	
	# Load CNC port IDs
	df_cnc = pd.read_csv('src/cma/res/input/Port_Productivity.csv')
	cnc_port_ids = set(df_cnc['portid'])
	
	# Get finer pool ports
	finer_ports = {p.get_id() for p in port_pool_finer.tolist_port()}
	
	# Legacy ports = finer ports - CNC ports
	legacy_in_finer = finer_ports - cnc_port_ids
	
	# Should have ~126 legacy ports (some ports may not have operational data)
	# Original finer pool had 93 ports, now with 56 CNC we should have more
	assert len(legacy_in_finer) > 0, "No legacy ports in finer pool"
	assert len(finer_ports) > 56, "Finer pool should have more than just 56 CNC ports"
	
	print(f"✓ Finer pool has {len(finer_ports)} ports: 56 CNC + {len(legacy_in_finer)} legacy")


def test_legacy_ports_skip_old_ranks():
	"""Test that legacy ports only have ranks 1-11 (skip old ranks 12-13)"""
	port_pool, port_pool_finer = read_port_data()
	
	# Load CNC port IDs
	df_cnc = pd.read_csv('src/cma/res/input/Port_Productivity.csv')
	cnc_port_ids = set(df_cnc['portid'])
	
	# Get a legacy port with operational data
	finer_ports = port_pool_finer.tolist_port()
	legacy_ports = [p for p in finer_ports if p.get_id() not in cnc_port_ids]
	
	assert len(legacy_ports) > 0, "No legacy ports found for testing"
	
	# Check legacy ports don't have ranks > 11
	for port in legacy_ports:
		for rank in port.fit_vessel_ranks.keys():
			assert rank <= 11, \
				f"Legacy port {port.get_id()} has old rank {rank} > 11"
		for rank in port.berth_productivity.keys():
			assert rank <= 11, \
				f"Legacy port {port.get_id()} has productivity for old rank {rank} > 11"
		for rank in port.cost_portcall.keys():
			assert rank <= 11, \
				f"Legacy port {port.get_id()} has cost for old rank {rank} > 11"
	
	print(f"✓ All legacy ports filtered to ranks 1-11 only (old ranks 12-13 excluded)")


def test_legacy_ports_no_waiting_times():
	"""Test that legacy (non-CNC) ports don't have waiting/maneuvering attributes"""
	port_pool, port_pool_finer = read_port_data()
	
	# Load CNC port IDs
	df_cnc = pd.read_csv('src/cma/res/input/Port_Productivity.csv')
	cnc_port_ids = set(df_cnc['portid'])
	
	# Get legacy ports
	finer_ports = port_pool_finer.tolist_port()
	legacy_ports = [p for p in finer_ports if p.get_id() not in cnc_port_ids]
	
	assert len(legacy_ports) > 0, "No legacy ports found for testing"
	
	# Legacy ports should NOT have waiting/maneuvering attributes
	for port in legacy_ports:
		assert not hasattr(port, 'waiting_time'), \
			f"Legacy port {port.get_id()} has unexpected waiting_time attribute"
		assert not hasattr(port, 'maneuvering_time_in'), \
			f"Legacy port {port.get_id()} has unexpected maneuvering_time_in attribute"
		assert not hasattr(port, 'maneuvering_time_out'), \
			f"Legacy port {port.get_id()} has unexpected maneuvering_time_out attribute"
	
	print(f"✓ Legacy ports don't have waiting/maneuvering attributes (CNC-only feature)")


def test_major_ports_accessible():
	"""Test that major ports (Shanghai, Singapore, Hong Kong) are accessible"""
	port_pool, port_pool_finer = read_port_data()
	
	major_ports = ['CNSHA', 'SGSIN', 'HKHKG']
	
	for port_id in major_ports:
		# Should be in main pool
		port = port_pool.get_port(port_id)
		assert port is not None, f"Major port {port_id} not found in main pool"
		
		# Should be in finer pool (all are CNC ports)
		finer_ids = {p.get_id() for p in port_pool_finer.tolist_port()}
		assert port_id in finer_ids, f"Major port {port_id} not in finer pool"
	
	print(f"✓ Major ports (Shanghai, Singapore, Hong Kong) accessible in both pools")


def test_dummy_value_handling():
	"""Test that dummy values (5000, 1000000) are converted to 0"""
	port_pool, _ = read_port_data()
	
	# Load CSV to find ports with dummy values
	df = pd.read_csv('src/cma/res/input/Port_Dataset.csv')
	
	dummy_transship = df[df['TranshipmentCost'] == 5000]['PortID'].tolist()
	dummy_storage = df[df['StorageCost'] == 1000000]['PortID'].tolist()
	
	# Verify these ports have 0 cost in loaded data
	for port_id in dummy_transship[:5]:  # Test first 5
		port = port_pool.get_port(port_id)
		assert port.cost_transship == 0, \
			f"Port {port_id} transship dummy not converted: {port.cost_transship}"
	
	for port_id in dummy_storage[:5]:  # Test first 5
		port = port_pool.get_port(port_id)
		assert port.cost_storage == 0, \
			f"Port {port_id} storage dummy not converted: {port.cost_storage}"
	
	print(f"✓ Dummy values (5000→0, 1000000→0) handled correctly")


def test_port_pool_methods():
	"""Test PortPool methods work correctly"""
	port_pool, port_pool_finer = read_port_data()
	
	# Test get_number_of_ports
	assert port_pool.get_number_of_ports() == 182
	assert port_pool_finer.get_number_of_ports() > 56  # At least 56 CNC ports
	
	# Test get_port
	port = port_pool.get_port('CNSHA')
	assert port.get_id() == 'CNSHA'
	
	# Test get_port_by_idx
	port_idx = port_pool.get_port_by_idx(0)
	assert port_idx is not None
	
	# Test tolist_port
	all_ports = port_pool.tolist_port()
	assert len(all_ports) == 182
	
	print(f"✓ PortPool methods (get_number_of_ports, get_port, get_port_by_idx, tolist_port) work")


def test_backward_compatibility():
	"""Test that function signature and return types haven't changed"""
	result = read_port_data()
	
	# Should return tuple of 2 elements
	assert isinstance(result, tuple), "read_port_data should return tuple"
	assert len(result) == 2, "read_port_data should return 2-tuple"
	
	port_pool, port_pool_finer = result
	
	# Both should be PortPool instances
	from cma.port import PortPool
	assert isinstance(port_pool, PortPool), "First return should be PortPool"
	assert isinstance(port_pool_finer, PortPool), "Second return should be PortPool"
	
	print(f"✓ Backward compatibility maintained: returns (PortPool, PortPool)")


def test_cnc_shanghai_complete_data():
	"""Test Shanghai (CNSHA) as a known CNC port with complete data"""
	port_pool, _ = read_port_data()
	
	shanghai = port_pool.get_port('CNSHA')
	
	# Check basic attributes
	assert shanghai.get_id() == 'CNSHA'
	lon, lat = shanghai.get_location()
	assert -180 <= lon <= 180, f"Invalid longitude: {lon}"
	assert -90 <= lat <= 90, f"Invalid latitude: {lat}"
	
	# Check operational data for all 11 ranks
	for rank in range(1, 12):
		assert rank in shanghai.fit_vessel_ranks
		assert shanghai.fit_vessel_ranks[rank] == 99999  # Unlimited
		
		assert rank in shanghai.berth_productivity
		assert shanghai.berth_productivity[rank] > 0
		
		assert rank in shanghai.cost_portcall
		assert shanghai.cost_portcall[rank] > 0
		
		assert rank in shanghai.waiting_time
		assert shanghai.waiting_time[rank] >= 0
	
	# Check maneuvering times
	assert shanghai.maneuvering_time_in > 0
	assert shanghai.maneuvering_time_out > 0
	
	print(f"✓ Shanghai (CNSHA) has complete CNC data: 11 ranks + waiting + maneuvering")


if __name__ == '__main__':
	print("Testing Hybrid Port Data Function...\n")
	
	test_port_pools_loaded()
	test_all_182_ports_in_main_pool()
	test_cnc_ports_in_finer_pool()
	test_cnc_ports_have_11_ranks()
	test_cnc_ports_have_waiting_and_maneuvering()
	test_legacy_ports_in_finer_pool()
	test_legacy_ports_skip_old_ranks()
	test_legacy_ports_no_waiting_times()
	test_major_ports_accessible()
	test_dummy_value_handling()
	test_port_pool_methods()
	test_backward_compatibility()
	test_cnc_shanghai_complete_data()
	
	print("\n" + "="*70)
	print("ALL HYBRID PORT DATA FUNCTION TESTS PASSED!")
	print("="*70)
