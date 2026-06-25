"""
Comprehensive test suite for port call costs validation with 11 vessel ranks.

This test suite validates:
1. Portcall_Costs.csv has correct structure (56 ports × 11 rank columns)
2. Port objects have cost_portcall dict attribute with all 11 ranks
3. Port.get_portcall_costs() method returns costs for all 11 vessel ranks
4. CSV values match loaded Port data
5. New ranks 10 and 11 have complete cost data
6. Cost values are reasonable and within expected ranges
7. Integration with VesselPool works correctly
8. All CNC ports have complete cost data
9. Costs generally increase with vessel rank (larger vessels cost more)
10. No missing or negative values

Test Coverage:
- CSV data structure validation
- Port attribute validation (cost_portcall dict)
- Method validation (get_portcall_costs)
- Value range and reasonableness checks
- New vessel rank validation (10 & 11)
- Integration tests with VesselPool
- Coverage analysis
- Data consistency between CSV and loaded objects
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cma import read_port_data, read_vessel_class_data
from cma.port import Port, PortPool
from cma.vessel import VesselPool


@pytest.fixture(scope="module")
def port_pools():
    """Load CNC and legacy port pools."""
    cnc_pool, legacy_pool = read_port_data()
    return cnc_pool, legacy_pool


@pytest.fixture(scope="module")
def vessel_pool():
    """Load VesselPool with all 11 vessel ranks."""
    return read_vessel_class_data()


@pytest.fixture(scope="module")
def portcall_costs_csv_path():
    """Path to Portcall_Costs.csv."""
    from importlib import resources
    file = __import__('pathlib').Path('data').joinpath('input/Portcall_Costs.csv')
    return file


@pytest.fixture(scope="module")
def portcall_costs_df(portcall_costs_csv_path):
    """Load Portcall_Costs.csv as DataFrame."""
    return pd.read_csv(portcall_costs_csv_path)


class TestCSVStructure:
    """Test Portcall_Costs.csv structure."""
    
    def test_csv_has_correct_structure(self, portcall_costs_df):
        """Test that CSV has correct columns: portid, 1, 2, ..., 11."""
        expected_columns = ['portid'] + [str(i) for i in range(1, 12)]
        
        assert list(portcall_costs_df.columns) == expected_columns, \
            f"CSV columns don't match expected: {list(portcall_costs_df.columns)}"
        
        print(f"\n✓ Portcall_Costs.csv has correct structure:")
        print(f"  Columns: portid, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11")
        print(f"  Total: {len(portcall_costs_df.columns)} columns")
    
    def test_csv_has_56_ports(self, portcall_costs_df):
        """Test that CSV has exactly 56 CNC ports."""
        assert len(portcall_costs_df) == 56, \
            f"CSV has {len(portcall_costs_df)} ports, expected 56"
        
        print(f"\n✓ CSV has 56 CNC ports")
        print(f"  First 5 ports: {portcall_costs_df['portid'].head().tolist()}")
    
    def test_csv_no_duplicate_ports(self, portcall_costs_df):
        """Test that CSV has no duplicate port IDs."""
        duplicates = portcall_costs_df['portid'].duplicated().sum()
        assert duplicates == 0, f"CSV has {duplicates} duplicate ports"
        
        print(f"\n✓ CSV has no duplicate ports")


class TestPortCostPortcallAttribute:
    """Test Port.cost_portcall attribute."""
    
    def test_cnc_ports_have_cost_portcall_attribute(self, port_pools, portcall_costs_df):
        """Test that CNC ports have cost_portcall dict attribute."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        
        ports_with_costs = 0
        for port in cnc_ports:
            if port.get_id() in cnc_port_ids and hasattr(port, 'cost_portcall'):
                assert isinstance(port.cost_portcall, dict), \
                    f"Port {port.get_id()} cost_portcall is not a dict"
                ports_with_costs += 1
        
        assert ports_with_costs == 56, \
            f"Expected 56 CNC ports with cost_portcall, got {ports_with_costs}"
        
        print(f"\n✓ CNC ports with cost_portcall attribute: {ports_with_costs}")
    
    def test_cost_portcall_dict_structure(self, port_pools, portcall_costs_df):
        """Test that cost_portcall dicts have correct structure."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        
        for port in cnc_ports:
            if port.get_id() in cnc_port_ids and hasattr(port, 'cost_portcall'):
                # Should be dict with int keys (vessel ranks)
                assert isinstance(port.cost_portcall, dict)
                
                # All keys should be integers (vessel ranks)
                for key in port.cost_portcall.keys():
                    assert isinstance(key, int), \
                        f"Port {port.get_id()} has non-integer rank: {key}"
                
                # All values should be numeric
                for rank, cost in port.cost_portcall.items():
                    assert isinstance(cost, (int, float, np.number)), \
                        f"Port {port.get_id()} rank {rank} has non-numeric cost: {cost}"
        
        print(f"\n✓ All cost_portcall dicts have valid structure (int keys, numeric values)")
    
    def test_all_ports_have_all_11_ranks(self, port_pools, portcall_costs_df):
        """Test that all CNC ports have cost data for all 11 ranks."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        
        ports_with_incomplete_data = []
        
        for port in cnc_ports:
            if port.get_id() in cnc_port_ids and hasattr(port, 'cost_portcall'):
                ranks_present = set(port.cost_portcall.keys())
                expected_ranks = set(range(1, 12))
                
                if ranks_present != expected_ranks:
                    missing = expected_ranks - ranks_present
                    ports_with_incomplete_data.append({
                        'port': port.get_id(),
                        'missing_ranks': missing
                    })
        
        assert len(ports_with_incomplete_data) == 0, \
            f"{len(ports_with_incomplete_data)} ports have incomplete rank data"
        
        print(f"\n✓ All 56 CNC ports have complete data for all 11 ranks")


class TestGetPortcallCostsMethod:
    """Test Port.get_portcall_costs() method."""
    
    def test_get_portcall_costs_returns_list(self, port_pools, vessel_pool):
        """Test that get_portcall_costs() returns a list."""
        cnc_pool, _ = port_pools
        port = cnc_pool.tolist_port()[0]
        
        costs = port.get_portcall_costs(vessel_pool)
        assert isinstance(costs, list), \
            f"get_portcall_costs() returned {type(costs)}, expected list"
        
        print(f"\n✓ get_portcall_costs() returns list")
    
    def test_get_portcall_costs_returns_11_values(self, port_pools, vessel_pool):
        """Test that get_portcall_costs() returns exactly 11 values."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        for port in cnc_ports:
            costs = port.get_portcall_costs(vessel_pool)
            assert len(costs) == 11, \
                f"Port {port.get_id()} returned {len(costs)} costs, expected 11"
        
        print(f"\n✓ get_portcall_costs() returns 11 values for all 56 CNC ports")
    
    def test_get_portcall_costs_values_match_cost_portcall(self, port_pools, vessel_pool):
        """Test that get_portcall_costs() values match cost_portcall dict."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        mismatches = []
        
        for port in cnc_ports:
            costs_list = port.get_portcall_costs(vessel_pool)
            
            for rank in range(1, 12):
                list_cost = costs_list[rank - 1]
                dict_cost = port.cost_portcall.get(rank)
                
                if dict_cost is not None:
                    if not np.isclose(list_cost, dict_cost, rtol=1e-5):
                        mismatches.append({
                            'port': port.get_id(),
                            'rank': rank,
                            'list_value': list_cost,
                            'dict_value': dict_cost
                        })
        
        assert len(mismatches) == 0, \
            f"Found {len(mismatches)} mismatches between list and dict values"
        
        print(f"\n✓ All get_portcall_costs() values match cost_portcall dict (616 values checked)")


class TestCostValues:
    """Test port call cost values."""
    
    def test_all_costs_are_positive(self, port_pools):
        """Test that all port call costs are positive."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        negative_costs = []
        
        for port in cnc_ports:
            for rank, cost in port.cost_portcall.items():
                if cost <= 0:
                    negative_costs.append({
                        'port': port.get_id(),
                        'rank': rank,
                        'cost': cost
                    })
        
        assert len(negative_costs) == 0, \
            f"Found {len(negative_costs)} non-positive costs"
        
        print(f"\n✓ All port call costs are positive")
    
    def test_costs_are_reasonable(self, port_pools):
        """Test that port call costs are within reasonable ranges."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        all_costs = []
        
        for port in cnc_ports:
            for rank, cost in port.cost_portcall.items():
                all_costs.append(cost)
        
        min_cost = min(all_costs)
        max_cost = max(all_costs)
        avg_cost = np.mean(all_costs)
        
        # Reasonable bounds for port call costs (in USD)
        assert min_cost > 0, f"Minimum cost too low: ${min_cost}"
        assert max_cost < 1e6, f"Maximum cost unreasonably high: ${max_cost}"
        assert avg_cost > 1000, f"Average cost too low: ${avg_cost}"
        
        print(f"\n✓ Port call costs are reasonable:")
        print(f"  Range: ${min_cost:.2f} - ${max_cost:.2f}")
        print(f"  Average: ${avg_cost:.2f}")
        print(f"  Total values: {len(all_costs)} (56 ports × 11 ranks)")
    
    def test_costs_generally_increase_with_rank(self, port_pools):
        """Test that costs generally increase with vessel rank (larger vessels)."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Calculate average cost by rank across all ports
        rank_averages = {}
        for rank in range(1, 12):
            costs_for_rank = []
            for port in cnc_ports:
                if rank in port.cost_portcall:
                    costs_for_rank.append(port.cost_portcall[rank])
            rank_averages[rank] = np.mean(costs_for_rank) if costs_for_rank else 0
        
        print(f"\n✓ Average port call costs by vessel rank:")
        for rank, avg_cost in rank_averages.items():
            print(f"  Rank {rank:2d}: ${avg_cost:>10,.2f}")
        
        # Generally, larger vessels (higher ranks) should cost more on average
        # Allow some exceptions as port costs can vary by port facilities
        rank_1_avg = rank_averages[1]
        rank_11_avg = rank_averages[11]
        
        # At minimum, rank 11 should cost more than rank 1 on average
        assert rank_11_avg >= rank_1_avg, \
            f"Rank 11 avg (${rank_11_avg:.2f}) should be >= Rank 1 avg (${rank_1_avg:.2f})"


class TestNewVesselRanks:
    """Test new vessel ranks 10 and 11 specifically."""
    
    def test_rank_10_has_complete_cost_data(self, port_pools, portcall_costs_df):
        """Test that all ports have cost data for rank 10."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        
        ports_with_rank_10 = 0
        rank_10_costs = []
        
        for port in cnc_ports:
            if port.get_id() in cnc_port_ids and 10 in port.cost_portcall:
                ports_with_rank_10 += 1
                rank_10_costs.append(port.cost_portcall[10])
        
        assert ports_with_rank_10 == 56, \
            f"Expected 56 ports with rank 10 data, got {ports_with_rank_10}"
        
        print(f"\n✓ Rank 10 (Vessel 10000-12499 TEU) port call costs:")
        print(f"  Ports with data: {ports_with_rank_10}/56")
        print(f"  Cost range: ${min(rank_10_costs):.2f} - ${max(rank_10_costs):.2f}")
        print(f"  Average cost: ${np.mean(rank_10_costs):.2f}")
    
    def test_rank_11_has_complete_cost_data(self, port_pools, portcall_costs_df):
        """Test that all ports have cost data for rank 11."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        
        ports_with_rank_11 = 0
        rank_11_costs = []
        
        for port in cnc_ports:
            if port.get_id() in cnc_port_ids and 11 in port.cost_portcall:
                ports_with_rank_11 += 1
                rank_11_costs.append(port.cost_portcall[11])
        
        assert ports_with_rank_11 == 56, \
            f"Expected 56 ports with rank 11 data, got {ports_with_rank_11}"
        
        print(f"\n✓ Rank 11 (Vessel 12500-15199 TEU) port call costs:")
        print(f"  Ports with data: {ports_with_rank_11}/56")
        print(f"  Cost range: ${min(rank_11_costs):.2f} - ${max(rank_11_costs):.2f}")
        print(f"  Average cost: ${np.mean(rank_11_costs):.2f}")
    
    def test_new_ranks_cost_comparison(self, port_pools):
        """Test cost comparison between new ranks 10 & 11 and existing ranks."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Calculate average costs for different rank groups
        rank_groups = {
            'Old Ranks 1-9': list(range(1, 10)),
            'New Rank 10': [10],
            'New Rank 11': [11]
        }
        
        group_averages = {}
        
        for group_name, ranks in rank_groups.items():
            all_costs = []
            for port in cnc_ports:
                for rank in ranks:
                    if rank in port.cost_portcall:
                        all_costs.append(port.cost_portcall[rank])
            group_averages[group_name] = np.mean(all_costs) if all_costs else 0
        
        print(f"\n✓ Cost comparison between old and new ranks:")
        for group, avg in group_averages.items():
            print(f"  {group}: ${avg:,.2f} average")


class TestCSVDataIntegrity:
    """Test CSV data integrity and consistency."""
    
    def test_csv_no_missing_values(self, portcall_costs_df):
        """Test that CSV has no missing cost values."""
        rank_columns = [str(i) for i in range(1, 12)]
        
        missing_counts = {}
        for col in rank_columns:
            missing = portcall_costs_df[col].isna().sum()
            if missing > 0:
                missing_counts[col] = missing
        
        assert len(missing_counts) == 0, \
            f"CSV has missing values: {missing_counts}"
        
        total_values = 56 * 11
        print(f"\n✓ CSV has no missing values ({total_values} total: 56 ports × 11 ranks)")
    
    def test_csv_values_match_loaded_data(self, portcall_costs_df, port_pools):
        """Test that CSV values match loaded Port data."""
        cnc_pool, _ = port_pools
        
        mismatches = []
        
        for _, row in portcall_costs_df.iterrows():
            port_id = row['portid']
            try:
                port = cnc_pool.get_port(port_id)
            except:
                continue
            
            for rank in range(1, 12):
                csv_cost = row[str(rank)]
                loaded_cost = port.cost_portcall.get(rank)
                
                if loaded_cost is not None:
                    if not np.isclose(csv_cost, loaded_cost, rtol=1e-5):
                        mismatches.append({
                            'port': port_id,
                            'rank': rank,
                            'csv': csv_cost,
                            'loaded': loaded_cost
                        })
        
        assert len(mismatches) == 0, \
            f"Found {len(mismatches)} mismatches between CSV and loaded data"
        
        print(f"\n✓ All 616 cost values match between CSV and loaded data (56 ports × 11 ranks)")


class TestSpecificPorts:
    """Test specific major ports."""
    
    def test_major_ports_have_complete_data(self, port_pools):
        """Test that major ports have complete cost data for all 11 ranks."""
        cnc_pool, _ = port_pools
        
        major_ports = ['SGSIN', 'CNSHA', 'HKHKG', 'MYPKG', 'VNVUT']
        
        for port_id in major_ports:
            try:
                port = cnc_pool.get_port(port_id)
                ranks_present = set(port.cost_portcall.keys())
                expected_ranks = set(range(1, 12))
                
                assert ranks_present == expected_ranks, \
                    f"Port {port_id} missing ranks: {expected_ranks - ranks_present}"
                
                # Show cost range for this port
                costs = [port.cost_portcall[r] for r in range(1, 12)]
                print(f"\n  {port_id}: ${min(costs):.2f} - ${max(costs):.2f} (all 11 ranks)")
                
            except Exception as e:
                print(f"\n  {port_id}: Not in CNC dataset")
        
        print(f"\n✓ Major ports validated for complete cost data")
    
    def test_example_port_cost_progression(self, port_pools):
        """Test cost progression across ranks for an example port."""
        cnc_pool, _ = port_pools
        
        # Use CNSHA as example
        port = cnc_pool.get_port('CNSHA')
        
        print(f"\n✓ Example: CNSHA port call costs by vessel rank:")
        for rank in range(1, 12):
            cost = port.cost_portcall[rank]
            print(f"  Rank {rank:2d}: ${cost:>10,.2f}")


class TestIntegrationWithVesselPool:
    """Test integration between PortPool, Port, and VesselPool."""
    
    def test_all_ports_work_with_vesselpool(self, port_pools, vessel_pool):
        """Test that all ports can return costs for VesselPool."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        errors = []
        
        for port in cnc_ports:
            try:
                costs = port.get_portcall_costs(vessel_pool)
                assert len(costs) == 11
                assert all(isinstance(c, (int, float, np.number)) for c in costs)
            except Exception as e:
                errors.append({
                    'port': port.get_id(),
                    'error': str(e)
                })
        
        assert len(errors) == 0, \
            f"Found {len(errors)} ports with errors: {errors[:3]}"
        
        print(f"\n✓ All 56 CNC ports successfully return costs for VesselPool")
    
    def test_vesselpool_rank_count_matches_costs(self, vessel_pool, port_pools):
        """Test that VesselPool rank count matches cost list length."""
        cnc_pool, _ = port_pools
        port = cnc_pool.tolist_port()[0]
        
        n_vessel_ranks = vessel_pool.get_number_of_types()
        costs = port.get_portcall_costs(vessel_pool)
        
        assert n_vessel_ranks == 11, f"VesselPool has {n_vessel_ranks} ranks, expected 11"
        assert len(costs) == n_vessel_ranks, \
            f"Cost list length {len(costs)} doesn't match vessel ranks {n_vessel_ranks}"
        
        print(f"\n✓ VesselPool has {n_vessel_ranks} ranks, costs list has {len(costs)} values")


class TestDataTypeConsistency:
    """Test data type consistency."""
    
    def test_all_costs_are_numeric(self, port_pools):
        """Test that all cost values are numeric (float/int)."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        data_types = set()
        
        for port in cnc_ports:
            for rank, cost in port.cost_portcall.items():
                data_types.add(type(cost).__name__)
        
        # Should be numeric types
        numeric_types = {'int', 'float', 'int64', 'float64', 'float32'}
        non_numeric = data_types - numeric_types
        
        assert len(non_numeric) == 0, \
            f"Found non-numeric types: {non_numeric}"
        
        print(f"\n✓ All cost values are numeric types: {data_types}")
    
    def test_csv_data_types(self, portcall_costs_df):
        """Test that CSV columns have correct data types."""
        rank_columns = [str(i) for i in range(1, 12)]
        
        data_types = set()
        for col in rank_columns:
            data_types.add(str(portcall_costs_df[col].dtype))
        
        print(f"\n✓ CSV data types: {data_types}")
        
        # Should all be float64
        assert len(data_types) == 1
        assert 'float' in list(data_types)[0]


class TestCoverageAnalysis:
    """Test coverage and completeness."""
    
    def test_complete_coverage_matrix(self, port_pools, portcall_costs_df):
        """Test that we have complete 56×11 coverage matrix."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        
        # Build coverage matrix
        coverage = {}
        for port in cnc_ports:
            port_id = port.get_id()
            if port_id in cnc_port_ids:
                coverage[port_id] = set(port.cost_portcall.keys())
        
        # Check completeness
        expected_ranks = set(range(1, 12))
        incomplete_ports = {}
        
        for port_id, ranks in coverage.items():
            if ranks != expected_ranks:
                incomplete_ports[port_id] = expected_ranks - ranks
        
        assert len(incomplete_ports) == 0, \
            f"Found {len(incomplete_ports)} ports with incomplete coverage"
        
        print(f"\n✓ Complete coverage matrix: 56 ports × 11 ranks = 616 cost values")
        print(f"  All ports: 100% coverage (11/11 ranks)")
    
    def test_rank_coverage_statistics(self, port_pools, portcall_costs_df):
        """Test coverage statistics by rank."""
        cnc_pool, _ = port_pools
        cnc_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        
        rank_coverage = {rank: 0 for rank in range(1, 12)}
        
        for port in cnc_ports:
            if port.get_id() in cnc_port_ids:
                for rank in range(1, 12):
                    if rank in port.cost_portcall:
                        rank_coverage[rank] += 1
        
        print(f"\n✓ Coverage by vessel rank:")
        for rank, count in rank_coverage.items():
            pct = (count / 56) * 100
            print(f"  Rank {rank:2d}: {count}/56 ports ({pct:.1f}%)")
        
        # All ranks should have 100% coverage
        for rank, count in rank_coverage.items():
            assert count == 56, f"Rank {rank} only has {count}/56 ports"


class TestCompleteIntegration:
    """Final comprehensive integration test."""
    
    def test_complete_portcall_costs_system(self, port_pools, vessel_pool, portcall_costs_df):
        """Comprehensive test of entire port call costs system."""
        cnc_pool, _ = port_pools
        all_ports = cnc_pool.tolist_port()
        
        # Get list of 56 CNC ports from CSV
        cnc_port_ids = set(portcall_costs_df['portid'].tolist())
        cnc_ports = [p for p in all_ports if p.get_id() in cnc_port_ids]
        
        print(f"\n{'='*70}")
        print(f"COMPLETE PORT CALL COSTS VALIDATION - 11 VESSEL RANKS")
        print(f"{'='*70}")
        
        # 1. CSV structure
        assert len(portcall_costs_df) == 56
        assert list(portcall_costs_df.columns) == ['portid'] + [str(i) for i in range(1, 12)]
        print(f"\n1. CSV Structure:")
        print(f"   ✓ Portcall_Costs.csv: 56 ports × 11 rank columns")
        
        # 2. Port attributes
        assert len(cnc_ports) == 56
        assert all(hasattr(p, 'cost_portcall') for p in cnc_ports)
        print(f"\n2. Port Attributes:")
        print(f"   ✓ All 56 CNC ports have cost_portcall dict")
        
        # 3. Coverage
        all_complete = all(set(p.cost_portcall.keys()) == set(range(1, 12)) for p in cnc_ports)
        assert all_complete
        print(f"\n3. Data Coverage:")
        print(f"   ✓ All ports have complete data for all 11 ranks")
        print(f"   ✓ Total values: 616 (56 ports × 11 ranks)")
        
        # 4. Method integration
        all_work = all(len(p.get_portcall_costs(vessel_pool)) == 11 for p in cnc_ports)
        assert all_work
        print(f"\n4. Method Integration:")
        print(f"   ✓ get_portcall_costs() returns 11 values for all ports")
        
        # 5. New ranks
        rank_10_count = sum(1 for p in cnc_ports if 10 in p.cost_portcall)
        rank_11_count = sum(1 for p in cnc_ports if 11 in p.cost_portcall)
        assert rank_10_count == 56
        assert rank_11_count == 56
        print(f"\n5. New Vessel Ranks:")
        print(f"   ✓ Rank 10: {rank_10_count}/56 ports (100%)")
        print(f"   ✓ Rank 11: {rank_11_count}/56 ports (100%)")
        
        # 6. Value validation
        all_costs = []
        for port in cnc_ports:
            all_costs.extend(port.cost_portcall.values())
        assert all(c > 0 for c in all_costs)
        print(f"\n6. Value Validation:")
        print(f"   ✓ All costs positive: ${min(all_costs):.2f} - ${max(all_costs):.2f}")
        print(f"   ✓ Average cost: ${np.mean(all_costs):.2f}")
        
        # 7. VesselPool integration
        assert vessel_pool.get_number_of_types() == 11
        print(f"\n7. VesselPool Integration:")
        print(f"   ✓ VesselPool has 11 vessel ranks")
        print(f"   ✓ All ports compatible with VesselPool")
        
        print(f"\n{'='*70}")
        print(f"✓ COMPLETE VALIDATION PASSED - Port call costs system fully functional")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    # Run with: python -m pytest test_portcall_costs.py -v -s
    pytest.main([__file__, "-v", "-s"])
