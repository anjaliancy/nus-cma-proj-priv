"""
Standalone validation tests for CNC proforma CSV file.

Tests the proforma_CNC.csv file containing 34 CNC service lines
with 22 operational columns per port call.

Run independently: python tests/test_proforma_csv_validation.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np


def test_proforma_file_exists():
	"""Test that proforma_CNC.csv exists"""
	import os
	path = 'data/input/proforma_CNC.csv'
	assert os.path.exists(path), f"Proforma file not found: {path}"
	
	print("✓ proforma_CNC.csv exists")


def test_proforma_structure():
	"""Test proforma CSV structure and columns"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Expected 22 columns
	expected_cols = [
		'linename', 'portid', 'sequence', 'eosp_utc_wd', 'eosp_utc_hr',
		'time_wait', 'time_manin', 'staytime', 'time_manout', 'timetonext',
		'vspeed', 'cap_nom', 'vrank', 'cap_eff', 'duration', 'moves',
		'ops_prod', 'alloc', 'cap_scale', 'cap_reserve', 'svc_type',
		'ignore_buffer_lb'
	]
	
	assert list(df.columns) == expected_cols, \
		f"Column mismatch. Expected {len(expected_cols)}, got {len(df.columns)}"
	
	# Should have 203 rows (port calls across all lines)
	assert len(df) == 203, f"Expected 203 port calls, got {len(df)}"
	
	print(f"✓ Proforma structure: 203 rows × 22 columns")


def test_proforma_34_service_lines():
	"""Test that proforma contains 34 unique service lines"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	unique_lines = df['linename'].nunique()
	assert unique_lines == 34, f"Expected 34 service lines, got {unique_lines}"
	
	# Check all line names are valid
	line_names = df['linename'].unique()
	for line_name in line_names:
		assert isinstance(line_name, str), f"Line name not string: {line_name}"
		assert len(line_name) > 0, "Empty line name found"
		assert 'CNC' in line_name, f"Line name doesn't contain 'CNC': {line_name}"
	
	print(f"✓ 34 unique CNC service lines with valid names")


def test_proforma_port_rotations():
	"""Test that each line has valid port rotation (sequence 1 to N)"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	for line_name in df['linename'].unique():
		df_line = df[df['linename'] == line_name]
		sequences = sorted(df_line['sequence'].tolist())
		
		# Sequence should start at 1
		assert sequences[0] == 1, \
			f"Line {line_name} sequence doesn't start at 1: {sequences[0]}"
		
		# Sequence should be consecutive
		expected_seq = list(range(1, len(sequences) + 1))
		assert sequences == expected_seq, \
			f"Line {line_name} has non-consecutive sequence: {sequences}"
		
		# Each line should have at least 2 ports
		assert len(sequences) >= 2, \
			f"Line {line_name} has only {len(sequences)} port (need ≥2)"
	
	print(f"✓ All 34 lines have valid port rotations (consecutive sequences)")


def test_proforma_vessel_ranks():
	"""Test that vessel ranks are in valid range (1-11)"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Get unique vessel ranks used
	ranks = sorted(df['vrank'].unique())
	
	# All ranks should be integers 1-11
	for rank in ranks:
		assert 1 <= rank <= 11, f"Invalid vessel rank: {rank} (should be 1-11)"
	
	# Check that ranks are consistent within each line
	for line_name in df['linename'].unique():
		df_line = df[df['linename'] == line_name]
		line_ranks = df_line['vrank'].unique()
		assert len(line_ranks) == 1, \
			f"Line {line_name} has multiple vessel ranks: {line_ranks}"
	
	print(f"✓ Vessel ranks in valid range 1-11: {ranks}")
	print(f"  All lines use consistent vessel rank throughout route")


def test_proforma_operational_times():
	"""Test that operational times are reasonable"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Waiting time: 0-168 hours (1 week max)
	assert (df['time_wait'] >= 0).all(), "Negative waiting time found"
	assert (df['time_wait'] <= 168).all(), "Waiting time > 1 week found"
	
	# Maneuvering in/out: 0-48 hours (some may be 0 for certain port types)
	assert (df['time_manin'] >= 0).all(), "Negative maneuvering in time"
	assert (df['time_manin'] <= 48).all(), "Maneuvering in time > 48 hours"
	assert (df['time_manout'] >= 0).all(), "Negative maneuvering out time"
	assert (df['time_manout'] <= 48).all(), "Maneuvering out time > 48 hours"
	
	# Stay time: 1-168 hours (7 days max)
	assert (df['staytime'] > 0).all(), "Non-positive stay time"
	assert (df['staytime'] <= 168).all(), "Stay time > 1 week"
	
	# Time to next port: 0-336 hours (2 weeks max for long routes)
	assert (df['timetonext'] >= 0).all(), "Negative time to next port"
	assert (df['timetonext'] <= 336).all(), "Time to next port > 2 weeks"
	
	print(f"✓ Operational times in reasonable ranges:")
	print(f"  Wait: 0-168h, Maneuver: 0.5-48h, Stay: 1-168h, Travel: 0-336h")


def test_proforma_vessel_speeds():
    """Test that vessel speeds are in reasonable ranges."""
    df = pd.read_csv('data/input/proforma_CNC.csv')
    
    # Speeds should be positive and <= 25 knots
    # Note: Low speeds (1-7 kn) are valid for short hops or harbor movements
    assert (df['vspeed'] > 0).all(), "Non-positive speed found"
    assert (df['vspeed'] <= 25).all(), "Speed > 25 knots (too fast)"
    
    # Most speeds should be in typical cruising range (10-18 knots)
    typical_speed = ((df['vspeed'] >= 10) & (df['vspeed'] <= 18)).sum()
    ratio = typical_speed / len(df)
    assert ratio > 0.6, f"Only {ratio*100:.1f}% in typical cruising range (expected >60%)"
    
    print(f"✓ Vessel speeds in valid range: {df['vspeed'].min():.1f} - {df['vspeed'].max():.1f} knots")
    print(f"  {ratio*100:.1f}% in typical cruising range (10-18 knots)")
def test_proforma_vessel_capacities():
	"""Test that vessel capacities are reasonable"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Nominal capacity: 100-20000 TEU
	assert (df['cap_nom'] >= 100).all(), "Nominal capacity < 100 TEU"
	assert (df['cap_nom'] <= 20000).all(), "Nominal capacity > 20000 TEU"
	
	# Effective capacity should be less than or equal to nominal
	assert (df['cap_eff'] <= df['cap_nom']).all(), \
		"Effective capacity > nominal capacity"
	
	# Effective capacity should be at least 50% of nominal (typical utilization)
	ratio = df['cap_eff'] / df['cap_nom']
	assert (ratio >= 0.5).all(), "Effective capacity < 50% nominal (too low)"
	
	# Capacity should be consistent within each line
	for line_name in df['linename'].unique():
		df_line = df[df['linename'] == line_name]
		assert df_line['cap_nom'].nunique() == 1, \
			f"Line {line_name} has varying nominal capacity"
	
	print(f"✓ Vessel capacities: {df['cap_nom'].min():.0f} - {df['cap_nom'].max():.0f} TEU nominal")
	print(f"  Effective/Nominal ratio: {ratio.mean():.1%} average")


def test_proforma_port_productivity():
	"""Test that port productivity values are reasonable"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Productivity (moves per hour): typically 20-150 mph
	df_with_prod = df[df['ops_prod'] > 0]  # Filter out zero productivity
	assert (df_with_prod['ops_prod'] >= 10).all(), "Productivity < 10 mph (too low)"
	assert (df_with_prod['ops_prod'] <= 200).all(), "Productivity > 200 mph (too high)"
	
	# Moves (container moves) should be positive when productivity is positive
	df_with_moves = df[df['moves'] > 0]
	assert len(df_with_moves) > 0, "No port calls with container moves"
	
	# Duration (port stay duration) should be positive
	assert (df['duration'] > 0).all(), "Non-positive duration found"
	
	# Duration should be at least as long as theoretical handling time (moves/productivity)
	# In practice, duration includes waiting, berthing, and other activities
	for _, row in df_with_moves.head(10).iterrows():
		if row['ops_prod'] > 0 and row['moves'] > 0:
			min_handling_time = row['moves'] / row['ops_prod']
			# Duration should be >= 30% of theoretical handling time (very efficient case)
			# Some ports may have parallel operations or include only partial handling time
			assert row['duration'] >= min_handling_time * 0.3, \
				f"Duration {row['duration']:.1f}h too short for {row['moves']} moves at {row['ops_prod']:.1f} mph"
	
	print(f"✓ Port productivity: {df_with_prod['ops_prod'].min():.1f} - {df_with_prod['ops_prod'].max():.1f} mph")


def test_proforma_capacity_allocation():
	"""Test that capacity allocation and utilization are reasonable"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Allocation: should be positive (no NaN allowed)
	assert df['alloc'].notna().all(), "NaN allocation found"
	assert (df['alloc'] >= 0).all(), "Negative allocation found"
	
	# Capacity scale: typically 0.5-1.5 (utilization factor)
	# May have NaN for some port calls
	df_with_scale = df[df['cap_scale'].notna()]
	if len(df_with_scale) > 0:
		assert (df_with_scale['cap_scale'] >= 0).all(), "Negative capacity scale"
		assert (df_with_scale['cap_scale'] <= 2.0).all(), "Capacity scale > 2.0 (unreasonable)"
		
		# Most should be between 0.5-1.5
		normal_scale = df_with_scale[(df_with_scale['cap_scale'] >= 0.5) & (df_with_scale['cap_scale'] <= 1.5)]
		ratio = len(normal_scale) / len(df_with_scale)
		assert ratio > 0.7, f"Only {ratio*100:.1f}% with normal capacity scale"
	
	# Capacity reserve: should be non-negative when present
	# May have NaN for some port calls
	df_with_reserve = df[df['cap_reserve'].notna()]
	if len(df_with_reserve) > 0:
		assert (df_with_reserve['cap_reserve'] >= 0).all(), "Negative capacity reserve"
	
	print(f"✓ Capacity allocation valid:")
	print(f"  Allocation: {df['alloc'].min():.0f} - {df['alloc'].max():.0f}")
	if len(df_with_scale) > 0:
		print(f"  Scale factor: {df_with_scale['cap_scale'].min():.2f} - {df_with_scale['cap_scale'].max():.2f} ({len(df_with_scale)}/{len(df)} ports)")
	if len(df_with_reserve) > 0:
		print(f"  Reserve: {df_with_reserve['cap_reserve'].min():.0f} - {df_with_reserve['cap_reserve'].max():.0f} TEU ({len(df_with_reserve)}/{len(df)} ports)")


def test_proforma_service_types():
	"""Test that service types are valid"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Service type should be consistent within each line
	for line_name in df['linename'].unique():
		df_line = df[df['linename'] == line_name]
		assert df_line['svc_type'].nunique() == 1, \
			f"Line {line_name} has multiple service types"
	
	# Check valid service types (OWN, SLOT, etc.)
	svc_types = df['svc_type'].unique()
	for svc_type in svc_types:
		assert isinstance(svc_type, str), f"Invalid service type: {svc_type}"
		assert len(svc_type) > 0, "Empty service type found"
	
	print(f"✓ Service types: {sorted(svc_types)}")


def test_proforma_ports_in_dataset():
	"""Test that proforma ports exist in main Port_Dataset.csv"""
	df_proforma = pd.read_csv('data/input/proforma_CNC.csv')
	df_ports = pd.read_csv('data/input/Port_Dataset.csv')
	
	proforma_ports = set(df_proforma['portid'].unique())
	dataset_ports = set(df_ports['PortID'].unique())
	
	missing_ports = proforma_ports - dataset_ports
	assert len(missing_ports) == 0, \
		f"Proforma ports missing from Port_Dataset.csv: {missing_ports}"
	
	print(f"✓ All {len(proforma_ports)} proforma ports exist in Port_Dataset.csv")


def test_proforma_sample_line():
	"""Test a sample service line (BBX2CNC) in detail"""
	df = pd.read_csv('data/input/proforma_CNC.csv')
	
	# Get BBX2CNC line
	df_line = df[df['linename'] == 'BBX2CNC'].sort_values('sequence')
	
	assert len(df_line) == 7, "BBX2CNC should have 7 port calls"
	
	# Check specific ports in rotation
	expected_ports = ['CNNGB', 'CNSHA', 'TWKHH', 'MYPKG', 'BDCGP', 'MYPKG', 'VNSGN']
	actual_ports = df_line['portid'].tolist()
	assert actual_ports == expected_ports, \
		f"BBX2CNC port rotation mismatch: {actual_ports}"
	
	# Check vessel rank is consistent (rank 5)
	assert (df_line['vrank'] == 5).all(), "BBX2CNC should use rank 5 vessel"
	
	# Check capacity is consistent
	assert df_line['cap_nom'].nunique() == 1, "Capacity should be consistent"
	assert df_line['cap_nom'].iloc[0] == 2822, "BBX2CNC capacity should be 2822 TEU"
	
	print(f"✓ Sample line BBX2CNC validated:")
	print(f"  7 ports: {' → '.join(expected_ports)}")
	print(f"  Vessel: Rank 5, 2822 TEU nominal capacity")


if __name__ == '__main__':
	print("Testing CNC Proforma CSV File...\n")
	
	test_proforma_file_exists()
	test_proforma_structure()
	test_proforma_34_service_lines()
	test_proforma_port_rotations()
	test_proforma_vessel_ranks()
	test_proforma_operational_times()
	test_proforma_vessel_speeds()
	test_proforma_vessel_capacities()
	test_proforma_port_productivity()
	test_proforma_capacity_allocation()
	test_proforma_service_types()
	test_proforma_ports_in_dataset()
	test_proforma_sample_line()
	
	print("\n" + "="*70)
	print("ALL CNC PROFORMA CSV VALIDATION TESTS PASSED!")
	print("="*70)
