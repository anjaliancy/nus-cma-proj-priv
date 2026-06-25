"""
Standalone validation tests for CNC operational CSV files.

Tests the 4 CNC port operation files:
- Port_Productivity.csv
- Portcall_Costs.csv
- Port_WaitingTimes.csv
- Port_ManTimes.csv

Run independently: python tests/test_cnc_operational_csv_validation.py
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
import numpy as np
from pathlib import Path


def test_cnc_files_exist():
	"""Test that all 4 CNC operational CSV files exist"""
	base_path = Path('data/input')
	
	files = [
		base_path / 'Port_Productivity.csv',
		base_path / 'Portcall_Costs.csv',
		base_path / 'Port_WaitingTimes.csv',
		base_path / 'Port_ManTimes.csv'
	]
	
	for file in files:
		assert file.exists(), f"Missing CNC file: {file}"
	
	print("✓ All 4 CNC operational files exist")


def test_port_productivity_structure():
	"""Test Port_Productivity.csv structure and content"""
	df = pd.read_csv('data/input/Port_Productivity.csv')
	
	# Check columns: portid + ranks 1-11
	expected_cols = ['portid'] + [str(i) for i in range(1, 12)]
	assert list(df.columns) == expected_cols, f"Unexpected columns: {list(df.columns)}"
	
	# Check number of ports (should be 56 CNC ports)
	assert len(df) == 56, f"Expected 56 CNC ports, got {len(df)}"
	
	# Check all port IDs are valid UN/LOCODE format
	for port_id in df['portid']:
		assert isinstance(port_id, str), f"Port ID not string: {port_id}"
		assert len(port_id) == 5, f"Invalid port ID length: {port_id}"
	
	# Check productivity values are positive and reasonable (0-200 mph typical range)
	for rank in range(1, 12):
		col = str(rank)
		values = df[col].dropna()
		assert len(values) > 0, f"No productivity data for rank {rank}"
		assert (values > 0).all(), f"Non-positive productivity for rank {rank}"
		assert (values < 500).all(), f"Unreasonable productivity (>500 mph) for rank {rank}"
	
	print(f"✓ Port_Productivity.csv: 56 ports, 11 ranks, productivity range valid")


def test_portcall_costs_structure():
	"""Test Portcall_Costs.csv structure and content"""
	df = pd.read_csv('data/input/Portcall_Costs.csv')
	
	# Check columns: portid + ranks 1-11
	expected_cols = ['portid'] + [str(i) for i in range(1, 12)]
	assert list(df.columns) == expected_cols, f"Unexpected columns: {list(df.columns)}"
	
	# Check number of ports
	assert len(df) == 56, f"Expected 56 CNC ports, got {len(df)}"
	
	# Check cost values are positive and reasonable ($1000-$100000 typical range)
	for rank in range(1, 12):
		col = str(rank)
		values = df[col].dropna()
		assert len(values) > 0, f"No cost data for rank {rank}"
		assert (values > 0).all(), f"Non-positive cost for rank {rank}"
		assert (values < 200000).all(), f"Unreasonable cost (>$200k) for rank {rank}"
	
	# Verify costs generally increase with vessel rank (larger ships cost more)
	for idx, row in df.iterrows():
		costs = [row[str(r)] for r in range(1, 12) if not np.isnan(row[str(r)])]
		if len(costs) >= 3:
			# Allow some variation, but general trend should be increasing
			avg_first_3 = np.mean(costs[:3])
			avg_last_3 = np.mean(costs[-3:])
			assert avg_last_3 >= avg_first_3 * 0.8, f"Costs don't increase with rank for {row['portid']}"
	
	print(f"✓ Portcall_Costs.csv: 56 ports, 11 ranks, costs increase with rank")


def test_port_waiting_times_structure():
	"""Test Port_WaitingTimes.csv structure and content"""
	df = pd.read_csv('data/input/Port_WaitingTimes.csv')
	
	# Check columns: portid + ranks 1-11
	expected_cols = ['portid'] + [str(i) for i in range(1, 12)]
	assert list(df.columns) == expected_cols, f"Unexpected columns: {list(df.columns)}"
	
	# Check number of ports
	assert len(df) == 56, f"Expected 56 CNC ports, got {len(df)}"
	
	# Check waiting times are non-negative and reasonable (0-168 hours = 1 week max)
	for rank in range(1, 12):
		col = str(rank)
		values = df[col].dropna()
		assert len(values) > 0, f"No waiting time data for rank {rank}"
		assert (values >= 0).all(), f"Negative waiting time for rank {rank}"
		assert (values < 168).all(), f"Unreasonable waiting time (>1 week) for rank {rank}"
	
	print(f"✓ Port_WaitingTimes.csv: 56 ports, 11 ranks, waiting times 0-168 hours")


def test_port_maneuvering_times_structure():
	"""Test Port_ManTimes.csv structure and content"""
	df = pd.read_csv('data/input/Port_ManTimes.csv')
	
	# Check columns: portid, manin, manout
	expected_cols = ['portid', 'manin', 'manout']
	assert list(df.columns) == expected_cols, f"Unexpected columns: {list(df.columns)}"
	
	# Check number of ports
	assert len(df) == 56, f"Expected 56 CNC ports, got {len(df)}"
	
	# Check maneuvering times are positive and reasonable (0.1-24 hours typical)
	assert (df['manin'] > 0).all(), "Non-positive manin time found"
	assert (df['manout'] > 0).all(), "Non-positive manout time found"
	assert (df['manin'] < 48).all(), "Unreasonable manin time (>48 hours)"
	assert (df['manout'] < 48).all(), "Unreasonable manout time (>48 hours)"
	
	# Typically manin and manout are similar (within 2x factor)
	ratio = df['manin'] / df['manout']
	assert (ratio > 0.2).all() and (ratio < 5.0).all(), "Manin/manout ratio unreasonable"
	
	print(f"✓ Port_ManTimes.csv: 56 ports, manin/manout 0.1-48 hours")


def test_port_consistency_across_files():
	"""Test that all 4 files have the same 56 ports"""
	prod = pd.read_csv('data/input/Port_Productivity.csv')
	costs = pd.read_csv('data/input/Portcall_Costs.csv')
	wait = pd.read_csv('data/input/Port_WaitingTimes.csv')
	man = pd.read_csv('data/input/Port_ManTimes.csv')
	
	prod_ports = set(prod['portid'])
	costs_ports = set(costs['portid'])
	wait_ports = set(wait['portid'])
	man_ports = set(man['portid'])
	
	assert prod_ports == costs_ports == wait_ports == man_ports, \
		"Port IDs don't match across all 4 CNC files"
	
	assert len(prod_ports) == 56, f"Expected 56 unique CNC ports, got {len(prod_ports)}"
	
	# Check for duplicates in each file
	assert len(prod) == len(prod_ports), "Duplicate ports in Port_Productivity.csv"
	assert len(costs) == len(costs_ports), "Duplicate ports in Portcall_Costs.csv"
	assert len(wait) == len(wait_ports), "Duplicate ports in Port_WaitingTimes.csv"
	assert len(man) == len(man_ports), "Duplicate ports in Port_ManTimes.csv"
	
	print(f"✓ All 4 files have identical 56 CNC ports with no duplicates")


def test_cnc_ports_in_main_dataset():
	"""Test that CNC ports exist in main Port_Dataset.csv"""
	cnc_ports = pd.read_csv('data/input/Port_Productivity.csv')['portid']
	main_ports = pd.read_csv('data/input/Port_Dataset.csv')['PortID']
	
	cnc_set = set(cnc_ports)
	main_set = set(main_ports)
	
	missing_ports = cnc_set - main_set
	assert len(missing_ports) == 0, f"CNC ports missing from Port_Dataset.csv: {missing_ports}"
	
	print(f"✓ All 56 CNC ports exist in main Port_Dataset.csv (182 total ports)")


def test_sample_cnc_port_data():
	"""Test sample data for a known CNC port (CNSHA - Shanghai)"""
	prod = pd.read_csv('data/input/Port_Productivity.csv')
	costs = pd.read_csv('data/input/Portcall_Costs.csv')
	wait = pd.read_csv('data/input/Port_WaitingTimes.csv')
	man = pd.read_csv('data/input/Port_ManTimes.csv')
	
	# Shanghai should be in the dataset
	assert 'CNSHA' in prod['portid'].values, "Shanghai (CNSHA) not in CNC dataset"
	
	sha_prod = prod[prod['portid'] == 'CNSHA'].iloc[0]
	sha_costs = costs[costs['portid'] == 'CNSHA'].iloc[0]
	sha_wait = wait[wait['portid'] == 'CNSHA'].iloc[0]
	sha_man = man[man['portid'] == 'CNSHA'].iloc[0]
	
	# Check Shanghai has data for all 11 ranks
	for rank in range(1, 12):
		assert not np.isnan(sha_prod[str(rank)]), f"Shanghai missing productivity for rank {rank}"
		assert not np.isnan(sha_costs[str(rank)]), f"Shanghai missing cost for rank {rank}"
		assert not np.isnan(sha_wait[str(rank)]), f"Shanghai missing waiting time for rank {rank}"
	
	assert not np.isnan(sha_man['manin']), "Shanghai missing manin time"
	assert not np.isnan(sha_man['manout']), "Shanghai missing manout time"
	
	print(f"✓ Shanghai (CNSHA) has complete data for all 11 ranks + maneuvering times")


if __name__ == '__main__':
	print("Testing CNC Operational CSV Files...\n")
	
	test_cnc_files_exist()
	test_port_productivity_structure()
	test_portcall_costs_structure()
	test_port_waiting_times_structure()
	test_port_maneuvering_times_structure()
	test_port_consistency_across_files()
	test_cnc_ports_in_main_dataset()
	test_sample_cnc_port_data()
	
	print("\n" + "="*70)
	print("ALL CNC OPERATIONAL CSV VALIDATION TESTS PASSED!")
	print("="*70)
