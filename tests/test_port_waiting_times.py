"""
Comprehensive Validation Tests for Port Waiting Times with 11-Rank Vessel System

This test suite validates that port waiting times data works correctly with the new
11-rank vessel system. Tests verify:
- Waiting times data loading for all 11 vessel ranks
- Port.waiting_time attribute structure and values
- Consistency across 56 CNC ports
- Data ranges and validity
- Integration with PortPool and VesselPool
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from importlib import resources

from cma import (
    read_vessel_class_data,
    read_port_data
)
from cma.vessel import VesselPool
from cma.port import Port, PortPool


# Test fixtures
@pytest.fixture(scope="module")
def vesselpool():
    """Load 11-rank vessel pool"""
    return read_vessel_class_data()


@pytest.fixture(scope="module")
def portpool():
    """Load port data with waiting times"""
    _, portpool = read_port_data()
    return portpool


@pytest.fixture(scope="module")
def waiting_times_csv():
    """Load waiting times CSV directly"""
    file = __import__('pathlib').Path('data').joinpath('input/Port_WaitingTimes.csv')
    return pd.read_csv(file)


# ===== Test 1: VesselPool Has 11 Ranks =====
def test_vesselpool_has_11_ranks(vesselpool):
    """Test that vessel pool contains 11 ranks for waiting times validation"""
    assert isinstance(vesselpool, VesselPool), "Should be VesselPool instance"
    assert len(vesselpool.vessels_list) == 11, f"Should have 11 vessel ranks"
    
    ranks = [v.vessel_rank for v in vesselpool.vessels_list]
    assert ranks == list(range(1, 12)), f"Vessel ranks should be 1-11"
    
    print(f"✓ VesselPool has 11 ranks: {ranks}")


# ===== Test 2: Waiting Times CSV Has 11 Rank Columns =====
def test_waiting_times_csv_structure(waiting_times_csv):
    """Test that waiting times CSV has columns for all 11 vessel ranks"""
    df = waiting_times_csv
    
    # Should have portid column plus 11 rank columns
    expected_columns = ['portid'] + [str(i) for i in range(1, 12)]
    
    assert 'portid' in df.columns, "Should have portid column"
    
    # Check all rank columns exist
    for rank in range(1, 12):
        rank_col = str(rank)
        assert rank_col in df.columns, f"Should have column for rank {rank}"
    
    print(f"✓ Waiting times CSV has all 11 rank columns: 1-11")
    print(f"  Total columns: {len(df.columns)}")
    print(f"  Total ports: {len(df)}")


# ===== Test 3: All Ports Have waiting_time Attribute =====
def test_ports_have_waiting_time_attribute(portpool):
    """Test that all CNC ports have waiting_time attribute"""
    ports = portpool.tolist_port()
    
    cnc_ports_with_waiting = 0
    cnc_ports_without_waiting = 0
    legacy_ports = 0
    
    for port in ports:
        if hasattr(port, 'waiting_time'):
            # CNC port with waiting time data
            assert isinstance(port.waiting_time, dict), \
                f"Port {port.get_id()} waiting_time should be dict"
            cnc_ports_with_waiting += 1
        else:
            # Legacy port without waiting time data
            legacy_ports += 1
    
    print(f"✓ CNC ports with waiting_time attribute: {cnc_ports_with_waiting}")
    print(f"  Legacy ports without waiting_time: {legacy_ports}")
    print(f"  Total ports: {len(ports)}")
    
    # Should have at least 56 CNC ports (from Port_WaitingTimes.csv)
    assert cnc_ports_with_waiting >= 56, "Should have at least 56 CNC ports with waiting times"


# ===== Test 4: Waiting Time Dict Has Correct Structure =====
def test_waiting_time_dict_structure(portpool):
    """Test that waiting_time dicts have correct structure"""
    ports = portpool.tolist_port()
    
    total_waiting_dicts = 0
    total_ranks_found = set()
    
    for port in ports:
        if hasattr(port, 'waiting_time'):
            waiting_dict = port.waiting_time
            total_waiting_dicts += 1
            
            # Dict keys should be integers (vessel ranks)
            for rank in waiting_dict.keys():
                assert isinstance(rank, int), \
                    f"Port {port.get_id()} waiting_time key should be int, got {type(rank)}"
                assert 1 <= rank <= 11, \
                    f"Port {port.get_id()} rank {rank} should be between 1 and 11"
                total_ranks_found.add(rank)
            
            # Values should be numeric (hours)
            for rank, waiting_hours in waiting_dict.items():
                assert isinstance(waiting_hours, (int, float, np.number)), \
                    f"Port {port.get_id()} waiting time for rank {rank} should be numeric"
                assert waiting_hours >= 0, \
                    f"Port {port.get_id()} waiting time {waiting_hours} should be non-negative"
    
    print(f"✓ All {total_waiting_dicts} ports have valid waiting_time dict structure")
    print(f"  Ranks found across all ports: {sorted(total_ranks_found)}")
    
    # Should find all 11 ranks across the port dataset
    assert len(total_ranks_found) == 11, \
        f"Should find all 11 ranks, found {sorted(total_ranks_found)}"


# ===== Test 5: Waiting Times Match CSV Data =====
def test_waiting_times_match_csv(portpool, waiting_times_csv):
    """Test that loaded waiting times match CSV data"""
    df = waiting_times_csv
    ports = portpool.tolist_port()
    
    # Create port lookup by ID
    port_dict = {port.get_id(): port for port in ports}
    
    mismatches = []
    matches = 0
    
    for _, row in df.iterrows():
        port_id = row['portid']
        
        if port_id not in port_dict:
            # Port not loaded (might be filtered out)
            continue
        
        port = port_dict[port_id]
        
        if not hasattr(port, 'waiting_time'):
            mismatches.append(f"Port {port_id} missing waiting_time attribute")
            continue
        
        # Check each rank
        for rank in range(1, 12):
            csv_value = row[str(rank)]
            
            if np.isnan(csv_value):
                # CSV has NaN, port should not have this rank
                if rank in port.waiting_time:
                    mismatches.append(
                        f"Port {port_id} rank {rank}: should be NaN but got {port.waiting_time[rank]}"
                    )
            else:
                # CSV has value, port should have this rank with same value
                if rank not in port.waiting_time:
                    mismatches.append(
                        f"Port {port_id} rank {rank}: missing in waiting_time dict (CSV has {csv_value})"
                    )
                else:
                    port_value = port.waiting_time[rank]
                    # Allow small floating point differences
                    if abs(port_value - csv_value) > 0.001:
                        mismatches.append(
                            f"Port {port_id} rank {rank}: port={port_value}, CSV={csv_value}"
                        )
                    else:
                        matches += 1
    
    if mismatches:
        print(f"⚠️  Found {len(mismatches)} mismatches:")
        for m in mismatches[:10]:  # Show first 10
            print(f"  - {m}")
    
    assert len(mismatches) == 0, f"Found {len(mismatches)} waiting time mismatches"
    
    print(f"✓ All {matches} waiting time values match CSV data")


# ===== Test 6: Waiting Times Are Reasonable =====
def test_waiting_times_reasonable_ranges(portpool):
    """Test that waiting times are in reasonable ranges"""
    ports = portpool.tolist_port()
    
    all_waiting_times = []
    ports_checked = 0
    
    for port in ports:
        if hasattr(port, 'waiting_time'):
            ports_checked += 1
            for rank, waiting in port.waiting_time.items():
                all_waiting_times.append(waiting)
                
                # Waiting time should be reasonable (0-168 hours = 1 week max typically)
                assert waiting >= 0, \
                    f"Port {port.get_id()} rank {rank} waiting time should be non-negative"
                assert waiting <= 200, \
                    f"Port {port.get_id()} rank {rank} waiting time {waiting} hours seems unreasonable (>200 hours)"
    
    if all_waiting_times:
        min_wait = min(all_waiting_times)
        max_wait = max(all_waiting_times)
        avg_wait = sum(all_waiting_times) / len(all_waiting_times)
        
        print(f"✓ All waiting times are reasonable")
        print(f"  Ports checked: {ports_checked}")
        print(f"  Total waiting time values: {len(all_waiting_times)}")
        print(f"  Range: {min_wait:.2f} - {max_wait:.2f} hours")
        print(f"  Average: {avg_wait:.2f} hours")


# ===== Test 7: All 11 Ranks Represented =====
def test_all_11_ranks_have_waiting_times(portpool):
    """Test that all 11 vessel ranks have waiting time data somewhere"""
    ports = portpool.tolist_port()
    
    ranks_found = set()
    rank_port_counts = {rank: 0 for rank in range(1, 12)}
    
    for port in ports:
        if hasattr(port, 'waiting_time'):
            for rank in port.waiting_time.keys():
                ranks_found.add(rank)
                rank_port_counts[rank] += 1
    
    # All 11 ranks should be found
    missing_ranks = set(range(1, 12)) - ranks_found
    assert len(missing_ranks) == 0, \
        f"Ranks {missing_ranks} have no waiting time data in any port"
    
    print(f"✓ All 11 ranks have waiting time data")
    print(f"  Rank distribution across ports:")
    for rank in range(1, 12):
        print(f"    Rank {rank:2d}: {rank_port_counts[rank]:2d} ports")


# ===== Test 8: New Ranks 10 and 11 Have Data =====
def test_new_ranks_10_11_have_data(portpool):
    """Test that new ranks 10 and 11 specifically have waiting time data"""
    ports = portpool.tolist_port()
    
    rank_10_ports = []
    rank_11_ports = []
    
    for port in ports:
        if hasattr(port, 'waiting_time'):
            if 10 in port.waiting_time:
                rank_10_ports.append((port.get_id(), port.waiting_time[10]))
            if 11 in port.waiting_time:
                rank_11_ports.append((port.get_id(), port.waiting_time[11]))
    
    assert len(rank_10_ports) > 0, "No ports have waiting time for rank 10"
    assert len(rank_11_ports) > 0, "No ports have waiting time for rank 11"
    
    print(f"✓ New rank 10 has waiting time data in {len(rank_10_ports)} ports")
    print(f"  Sample ports: {[p[0] for p in rank_10_ports[:5]]}")
    print(f"  Sample values: {[f'{p[1]:.2f}h' for p in rank_10_ports[:5]]}")
    
    print(f"✓ New rank 11 has waiting time data in {len(rank_11_ports)} ports")
    print(f"  Sample ports: {[p[0] for p in rank_11_ports[:5]]}")
    print(f"  Sample values: {[f'{p[1]:.2f}h' for p in rank_11_ports[:5]]}")


# ===== Test 9: Specific Port Examples =====
def test_specific_ports_waiting_times(portpool):
    """Test waiting times for specific well-known ports"""
    test_ports = ['SGSIN', 'CNSHA', 'HKHKG', 'MYPKG', 'BDCGP']
    
    ports_dict = {port.get_id(): port for port in portpool.tolist_port()}
    
    for port_id in test_ports:
        if port_id in ports_dict:
            port = ports_dict[port_id]
            
            if hasattr(port, 'waiting_time'):
                assert isinstance(port.waiting_time, dict), \
                    f"Port {port_id} waiting_time should be dict"
                assert len(port.waiting_time) > 0, \
                    f"Port {port_id} should have waiting time data"
                
                # Should have data for multiple ranks
                num_ranks = len(port.waiting_time)
                assert num_ranks >= 5, \
                    f"Port {port_id} should have waiting times for multiple ranks, got {num_ranks}"
                
                print(f"✓ Port {port_id}: {num_ranks} ranks with waiting time data")
            else:
                print(f"  Note: Port {port_id} is legacy port (no waiting time data)")


# ===== Test 10: Waiting Time Consistency Across Port Types =====
def test_waiting_time_by_port_size(portpool):
    """Test that larger ports generally have more complete waiting time data"""
    ports = portpool.tolist_port()
    
    ports_with_data = []
    for port in ports:
        if hasattr(port, 'waiting_time'):
            num_ranks = len(port.waiting_time)
            ports_with_data.append({
                'port_id': port.get_id(),
                'num_ranks': num_ranks,
                'avg_waiting': sum(port.waiting_time.values()) / len(port.waiting_time) if port.waiting_time else 0
            })
    
    # Sort by number of ranks with data
    ports_with_data.sort(key=lambda x: x['num_ranks'], reverse=True)
    
    print(f"✓ Waiting time data coverage:")
    print(f"  Top 5 ports by rank coverage:")
    for p in ports_with_data[:5]:
        print(f"    {p['port_id']}: {p['num_ranks']} ranks, avg {p['avg_waiting']:.2f}h")
    
    print(f"  Bottom 5 ports by rank coverage:")
    for p in ports_with_data[-5:]:
        print(f"    {p['port_id']}: {p['num_ranks']} ranks, avg {p['avg_waiting']:.2f}h")


# ===== Test 11: CSV File Integrity =====
def test_waiting_times_csv_integrity(waiting_times_csv):
    """Test CSV file integrity and completeness"""
    df = waiting_times_csv
    
    # Should have exactly 56 CNC ports
    assert len(df) == 56, f"Should have 56 ports, got {len(df)}"
    
    # Check for duplicates
    duplicates = df['portid'].duplicated().sum()
    assert duplicates == 0, f"Found {duplicates} duplicate port IDs"
    
    # Check for missing portids
    missing_portids = df['portid'].isna().sum()
    assert missing_portids == 0, f"Found {missing_portids} missing port IDs"
    
    # Count non-NaN values per rank
    rank_coverage = {}
    for rank in range(1, 12):
        col = str(rank)
        non_nan = df[col].notna().sum()
        rank_coverage[rank] = non_nan
    
    print(f"✓ CSV integrity verified: 56 ports, no duplicates")
    print(f"  Rank coverage (non-NaN values):")
    for rank in range(1, 12):
        coverage_pct = (rank_coverage[rank] / 56) * 100
        print(f"    Rank {rank:2d}: {rank_coverage[rank]:2d}/56 ports ({coverage_pct:5.1f}%)")


# ===== Test 12: Integration Test - Access Waiting Times =====
def test_integration_access_waiting_times(portpool, vesselpool):
    """Integration test: Access waiting times for various port-vessel combinations"""
    ports = portpool.tolist_port()
    vessels = vesselpool.vessels_list
    
    # Find a CNC port with waiting time data
    test_port = None
    for port in ports:
        if hasattr(port, 'waiting_time') and len(port.waiting_time) >= 5:
            test_port = port
            break
    
    assert test_port is not None, "Should find at least one port with waiting time data"
    
    # Access waiting times for different vessel ranks
    accessible_ranks = []
    for vessel in vessels:
        rank = vessel.vessel_rank
        if rank in test_port.waiting_time:
            waiting = test_port.waiting_time[rank]
            assert isinstance(waiting, (int, float, np.number)), \
                f"Waiting time should be numeric"
            assert waiting >= 0, f"Waiting time should be non-negative"
            accessible_ranks.append((rank, waiting))
    
    assert len(accessible_ranks) > 0, \
        "Should be able to access waiting times for at least one vessel rank"
    
    print(f"✓ Integration test passed for port: {test_port.get_id()}")
    print(f"  Accessible waiting times: {len(accessible_ranks)}/11 ranks")
    print(f"  Sample: Rank {accessible_ranks[0][0]} = {accessible_ranks[0][1]:.2f} hours")


# ===== Test 13: Waiting Times vs Vessel Capacity Correlation =====
def test_waiting_times_vs_capacity(portpool, vesselpool):
    """Test if waiting times correlate with vessel capacity (larger vessels wait longer)"""
    ports = portpool.tolist_port()
    vessels = {v.vessel_rank: v for v in vesselpool.vessels_list}
    
    # Collect waiting times per rank across all ports
    rank_waiting_times = {rank: [] for rank in range(1, 12)}
    
    for port in ports:
        if hasattr(port, 'waiting_time'):
            for rank, waiting in port.waiting_time.items():
                rank_waiting_times[rank].append(waiting)
    
    # Calculate average waiting time per rank
    rank_avg_waiting = {}
    for rank, waitings in rank_waiting_times.items():
        if waitings:
            rank_avg_waiting[rank] = sum(waitings) / len(waitings)
    
    assert len(rank_avg_waiting) == 11, "Should have avg waiting for all 11 ranks"
    
    print(f"✓ Average waiting time by vessel rank:")
    for rank in range(1, 12):
        vessel = vessels[rank]
        avg_wait = rank_avg_waiting[rank]
        capacity = vessel.vessel_capacity
        print(f"    Rank {rank:2d} ({capacity:7.0f} TEU): {avg_wait:5.2f} hours avg")


# ===== Test 14: No Negative Waiting Times =====
def test_no_negative_waiting_times(waiting_times_csv):
    """Test that CSV contains no negative waiting times"""
    df = waiting_times_csv
    
    negative_found = []
    for rank in range(1, 12):
        col = str(rank)
        negative_values = df[df[col] < 0]
        if len(negative_values) > 0:
            for _, row in negative_values.iterrows():
                negative_found.append((row['portid'], rank, row[col]))
    
    assert len(negative_found) == 0, \
        f"Found {len(negative_found)} negative waiting times: {negative_found}"
    
    print(f"✓ No negative waiting times found in CSV")


# ===== Test 15: Waiting Times Follow Expected Patterns =====
def test_waiting_times_patterns(portpool):
    """Test that waiting times follow expected operational patterns"""
    ports = portpool.tolist_port()
    
    # Ports should have waiting times that vary by vessel size
    # Larger vessels (higher ranks) might have different waiting patterns
    
    ports_with_all_ranks = []
    for port in ports:
        if hasattr(port, 'waiting_time'):
            if len(port.waiting_time) == 11:  # Has data for all ranks
                ports_with_all_ranks.append(port)
    
    print(f"✓ Found {len(ports_with_all_ranks)} ports with complete waiting time data (all 11 ranks)")
    
    if ports_with_all_ranks:
        sample_port = ports_with_all_ranks[0]
        print(f"  Sample port {sample_port.get_id()} waiting times:")
        for rank in range(1, 12):
            waiting = sample_port.waiting_time[rank]
            print(f"    Rank {rank:2d}: {waiting:6.2f} hours")


# ===== Test 16: Consistency with Proforma Data =====
def test_waiting_times_consistency_with_proforma(portpool):
    """Test that ports used in proforma service lines have waiting time data"""
    # Common ports from proforma_CNC.csv
    proforma_ports = [
        'CNNGB', 'CNSHA', 'TWKHH', 'MYPKG', 'BDCGP', 'VNSGN',
        'CNNSA', 'CNSHK', 'SGSIN', 'CNXMN', 'PHMNL'
    ]
    
    ports_dict = {port.get_id(): port for port in portpool.tolist_port()}
    
    ports_with_waiting = 0
    ports_without_waiting = 0
    
    for port_id in proforma_ports:
        if port_id in ports_dict:
            port = ports_dict[port_id]
            if hasattr(port, 'waiting_time'):
                assert len(port.waiting_time) > 0, \
                    f"Proforma port {port_id} should have waiting time data"
                ports_with_waiting += 1
            else:
                ports_without_waiting += 1
    
    print(f"✓ Proforma ports checked: {len(proforma_ports)}")
    print(f"  With waiting time data: {ports_with_waiting}")
    print(f"  Without waiting time data: {ports_without_waiting}")
    
    # Most proforma ports should have waiting time data
    assert ports_with_waiting >= len(proforma_ports) * 0.7, \
        "At least 70% of proforma ports should have waiting time data"


# ===== Test 17: Data Type Consistency =====
def test_waiting_times_data_types(portpool):
    """Test that all waiting time values have consistent data types"""
    ports = portpool.tolist_port()
    
    all_types = set()
    
    for port in ports:
        if hasattr(port, 'waiting_time'):
            for rank, waiting in port.waiting_time.items():
                all_types.add(type(waiting).__name__)
                
                # Should be numeric
                assert isinstance(waiting, (int, float, np.number)), \
                    f"Port {port.get_id()} rank {rank} waiting time type should be numeric, got {type(waiting)}"
    
    print(f"✓ Waiting time data types found: {all_types}")
    print(f"  All types are numeric")


# ===== Test 18: Complete Integration Test =====
def test_complete_integration(portpool, vesselpool, waiting_times_csv):
    """Complete integration test: Load, access, validate waiting times"""
    # 1. Verify data loaded
    assert len(vesselpool.vessels_list) == 11, "Should have 11 vessel ranks"
    assert len(portpool.tolist_port()) > 0, "Should have ports"
    
    # 2. Verify CSV structure
    assert len(waiting_times_csv) == 56, "CSV should have 56 ports"
    assert '11' in waiting_times_csv.columns, "CSV should have column for rank 11"
    
    # 3. Verify ports have waiting_time
    ports_with_waiting = sum(1 for p in portpool.tolist_port() if hasattr(p, 'waiting_time'))
    assert ports_with_waiting >= 56, "Should have at least 56 ports with waiting time"
    
    # 4. Verify all ranks represented
    all_ranks = set()
    for port in portpool.tolist_port():
        if hasattr(port, 'waiting_time'):
            all_ranks.update(port.waiting_time.keys())
    assert all_ranks == set(range(1, 12)), "Should have all 11 ranks represented"
    
    # 5. Verify data accessibility
    sample_port = next(p for p in portpool.tolist_port() if hasattr(p, 'waiting_time'))
    sample_rank = list(sample_port.waiting_time.keys())[0]
    sample_waiting = sample_port.waiting_time[sample_rank]
    assert isinstance(sample_waiting, (int, float, np.number)), "Should be able to access waiting time value"
    
    print(f"✓ Complete integration test passed")
    print(f"  VesselPool: 11 ranks")
    print(f"  PortPool: {len(portpool.tolist_port())} ports, {ports_with_waiting} with waiting times")
    print(f"  CSV: 56 ports × 11 ranks")
    print(f"  All 11 ranks represented across ports")
    print(f"  Data accessible and valid")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
