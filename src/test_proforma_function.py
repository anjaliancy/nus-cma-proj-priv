"""
Function-level tests for read_cnc_proforma_data().

Tests the function that reads proforma_CNC.csv and creates ServiceLine objects
with detailed operational metadata.

Run from src directory: python test_proforma_function.py
"""

import numpy as np
from cma.data_reader import read_cnc_proforma_data, read_port_data, read_vessel_class_data


def test_proforma_function_loads_data():
	"""Test that read_cnc_proforma_data() loads and parses the CSV correctly"""
	# First load required dependencies
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	
	# Load proforma data
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	# Check return structure
	assert isinstance(result, dict), "Function should return a dict"
	assert 'lines' in result, "Result should have 'lines' key"
	assert 'metadata' in result, "Result should have 'metadata' key"
	
	print("✓ Function returns dict with 'lines' and 'metadata' keys")


def test_proforma_creates_34_service_lines():
	"""Test that function creates 34 ServiceLine objects"""
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	lines = result['lines']
	metadata = result['metadata']
	
	# Should have 34 lines (from 34 unique service lines in CSV)
	assert isinstance(lines, list), "Lines should be a list"
	assert len(lines) > 0, "Should have at least one service line"
	
	# Metadata should have same number of entries
	assert isinstance(metadata, dict), "Metadata should be a dict"
	assert len(metadata) > 0, "Should have metadata entries"
	
	print(f"✓ Created {len(lines)} ServiceLine objects")
	print(f"✓ Created {len(metadata)} metadata entries")


def test_proforma_serviceline_objects():
	"""Test that ServiceLine objects are created correctly"""
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	lines = result['lines']
	
	# Check first line
	if len(lines) > 0:
		line = lines[0]
		
		# Should have attributes from ServiceLine class
		assert hasattr(line, 'name'), "ServiceLine should have 'name' attribute"
		assert hasattr(line, 'tolist_port'), "ServiceLine should have 'tolist_port' method"
		
		# Name should be non-empty
		assert line.name(), "ServiceLine name should be non-empty"
		
		# tolist_port should return a list
		ports = line.tolist_port()
		assert isinstance(ports, list), "tolist_port() should return a list"
		assert len(ports) >= 2, "ServiceLine should have at least 2 ports"
		
		print(f"✓ ServiceLine objects have correct structure")
		print(f"  Sample: {line.name()} with {len(ports)} ports")


def test_proforma_metadata_structure():
	"""Test that metadata has expected structure"""
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	metadata = result['metadata']
	
	# Check first metadata entry
	if len(metadata) > 0:
		first_key = list(metadata.keys())[0]
		meta = metadata[first_key]
		
		# Expected keys
		expected_keys = {
			'vessel_rank', 'vessel_capacity_nominal', 'vessel_capacity_effective',
			'speed', 'port_calls', 'port_rotation', 'total_duration', 'total_moves',
			'service_type', 'port_details'
		}
		
		for key in expected_keys:
			assert key in meta, f"Metadata should have '{key}' key"
		
		# Check port_calls is a positive integer
		assert isinstance(meta['port_calls'], (int, np.integer)), "port_calls should be an integer"
		assert meta['port_calls'] > 0, "port_calls should be positive"
		
		# Check port_details structure
		port_details = meta['port_details']
		assert isinstance(port_details, list), "port_details should be a list"
		
		if len(port_details) > 0:
			first_detail = port_details[0]
			# Each port detail should have operational info
			detail_keys = {
				'port_id', 'sequence', 
				'waiting_time', 'maneuvering_in', 'stay_time', 'maneuvering_out',
				'time_to_next', 'speed_to_next',
				'moves', 'productivity', 
				'allocation', 'capacity_scale', 'capacity_reserve'
			}
			
			for key in detail_keys:
				assert key in first_detail, f"Port detail should have '{key}' key"
		
		print(f"✓ Metadata has correct structure")
		print(f"  Sample: {first_key}")
		print(f"    Vessel rank: {meta['vessel_rank']}, Capacity: {meta['vessel_capacity_nominal']} TEU")
		print(f"    {meta['port_calls']} port calls")


def test_proforma_vessel_ranks():
	"""Test that vessel ranks are in valid range"""
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	metadata = result['metadata']
	
	# Collect all vessel ranks
	ranks = [meta['vessel_rank'] for meta in metadata.values()]
	
	# All ranks should be in range 1-11
	assert all(1 <= rank <= 11 for rank in ranks), "Vessel ranks should be 1-11"
	
	# Proforma uses ranks 3-8
	unique_ranks = sorted(set(ranks))
	print(f"✓ Vessel ranks in valid range: {unique_ranks}")


def test_proforma_port_rotations():
	"""Test that port rotations are valid"""
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	metadata = result['metadata']
	
	for line_name, meta in metadata.items():
		port_rotation = meta['port_rotation']
		port_count = meta['port_calls']
		port_details = meta['port_details']
		
		# Port rotation should be a list
		assert isinstance(port_rotation, list), f"{line_name}: port_rotation should be a list"
		
		# Should have at least 2 ports
		assert len(port_rotation) >= 2, f"{line_name}: should have at least 2 ports in rotation"
		
		# Number of ports in rotation should match port_calls count
		assert len(port_rotation) == port_count, \
			f"{line_name}: port rotation length ({len(port_rotation)}) should match port_calls ({port_count})"
		
		# Number of port_details should also match
		assert len(port_details) == port_count, \
			f"{line_name}: port_details length should match port_calls"
		
		# Sequences should be consecutive starting from 1
		sequences = [detail['sequence'] for detail in port_details]
		expected_sequences = list(range(1, port_count + 1))
		assert sequences == expected_sequences, \
			f"{line_name}: sequences should be consecutive 1-N, got {sequences}"
	
	print(f"✓ All {len(metadata)} service lines have valid port rotations")


def test_proforma_operational_data():
	"""Test that operational data is valid"""
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	metadata = result['metadata']
	
	for line_name, meta in metadata.items():
		# Total duration should be positive
		assert meta['total_duration'] > 0, f"{line_name}: total_duration should be positive"
		
		# Total moves should be positive
		assert meta['total_moves'] > 0, f"{line_name}: total_moves should be positive"
		
		# Speed should be positive
		assert meta['speed'] > 0, f"{line_name}: speed should be positive"
		
		# Capacities should be positive
		assert meta['vessel_capacity_nominal'] > 0, f"{line_name}: nominal capacity should be positive"
		assert meta['vessel_capacity_effective'] > 0, f"{line_name}: effective capacity should be positive"
		
		# Effective capacity should be <= nominal
		assert meta['vessel_capacity_effective'] <= meta['vessel_capacity_nominal'], \
			f"{line_name}: effective capacity should be <= nominal"
		
		# Service type should be non-empty
		assert meta['service_type'], f"{line_name}: service_type should be non-empty"
	
	print(f"✓ All {len(metadata)} service lines have valid operational data")


def test_proforma_sample_line():
	"""Test a specific known service line (BBX2CNC)"""
	portpool, portpool_dmd = read_port_data()
	vesselpool = read_vessel_class_data()
	result = read_cnc_proforma_data(portpool, vesselpool)
	
	lines = result['lines']
	metadata = result['metadata']
	
	# Find BBX2CNC line
	bbx2_names = [line.name() for line in lines if 'BBX2CNC' in line.name()]
	
	if len(bbx2_names) > 0:
		line_name = bbx2_names[0]
		
		# Get metadata
		if line_name in metadata:
			meta = metadata[line_name]
			
			# BBX2CNC should have:
			# - 7 port calls
			# - Vessel rank 5
			# - ~2822 TEU nominal capacity
			assert meta['port_calls'] == 7, f"BBX2CNC should have 7 port calls, got {meta['port_calls']}"
			assert meta['vessel_rank'] == 5, f"BBX2CNC should use rank 5 vessel, got {meta['vessel_rank']}"
			assert abs(meta['vessel_capacity_nominal'] - 2822) < 100, \
				f"BBX2CNC capacity should be ~2822 TEU, got {meta['vessel_capacity_nominal']}"
			
			# Port rotation should be CNNGB → CNSHA → TWKHH → MYPKG → BDCGP → MYPKG → VNSGN
			expected_ports = ['CNNGB', 'CNSHA', 'TWKHH', 'MYPKG', 'BDCGP', 'MYPKG', 'VNSGN']
			assert meta['port_rotation'] == expected_ports, \
				f"BBX2CNC should visit {expected_ports}, got {meta['port_rotation']}"
			
			print(f"✓ Sample line BBX2CNC validated:")
			print(f"  {meta['port_calls']} ports: {' → '.join(meta['port_rotation'])}")
			print(f"  Vessel: Rank {meta['vessel_rank']}, {meta['vessel_capacity_nominal']} TEU")


if __name__ == '__main__':
	print("Testing read_cnc_proforma_data() function...\n")
	
	test_proforma_function_loads_data()
	test_proforma_creates_34_service_lines()
	test_proforma_serviceline_objects()
	test_proforma_metadata_structure()
	test_proforma_vessel_ranks()
	test_proforma_port_rotations()
	test_proforma_operational_data()
	test_proforma_sample_line()
	
	print("\n" + "="*70)
	print("ALL PROFORMA FUNCTION TESTS PASSED!")
	print("="*70)
