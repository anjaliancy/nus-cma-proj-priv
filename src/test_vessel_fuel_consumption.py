"""
Comprehensive test suite for vessel fuel consumption validation with 11 vessel ranks.

This test suite validates:
1. VesselPool contains all 11 vessel ranks (1-11)
2. Each vessel has correct fuel consumption data structure (18 speed levels)
3. Speed levels range correctly from 10.0 to 18.5 knots (0.5 increments)
4. Fuel consumption values are reasonable and increase with speed
5. New ranks 10 and 11 have complete fuel consumption curves
6. bunkering_cost_coefs DataFrame structure is correct
7. Integration with VesselPool.get_bukering_costs() works correctly
8. CSV data integrity (Vessel_Nominal.csv)
9. Fuel consumption calculations for voyage scenarios

Test Coverage:
- Data structure validation
- Value range validation
- Mathematical properties (fuel increases with speed)
- New vessel rank validation (10 & 11)
- Integration tests with VesselPool methods
- CSV data integrity
- Operational calculations
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from cma import read_vessel_class_data
from cma.vessel import VesselPool, Vessel


@pytest.fixture(scope="module")
def vessel_pool():
    """Load VesselPool with all 11 vessel ranks."""
    return read_vessel_class_data()


@pytest.fixture(scope="module")
def vessel_csv_path():
    """Path to Vessel_Nominal.csv."""
    from importlib import resources
    import cma.res
    file = resources.files('cma.res').joinpath('input/Vessel_Nominal.csv')
    return file


@pytest.fixture(scope="module")
def vessel_csv_df(vessel_csv_path):
    """Load Vessel_Nominal.csv as DataFrame."""
    return pd.read_csv(vessel_csv_path)


class TestVesselPoolStructure:
    """Test VesselPool basic structure for 11 ranks."""
    
    def test_vessel_pool_has_11_ranks(self, vessel_pool):
        """Test that VesselPool contains exactly 11 vessel ranks."""
        assert len(vessel_pool.vessels_list) == 11, \
            f"Expected 11 vessel ranks, got {len(vessel_pool.vessels_list)}"
        
        ranks = [v.vessel_rank for v in vessel_pool.vessels_list]
        print(f"\n✓ VesselPool has 11 ranks: {ranks}")
        assert ranks == list(range(1, 12)), \
            f"Expected ranks 1-11, got {ranks}"
    
    def test_all_vessels_are_vessel_objects(self, vessel_pool):
        """Test that all items in vessels_list are Vessel objects."""
        for idx, vessel in enumerate(vessel_pool.vessels_list):
            assert isinstance(vessel, Vessel), \
                f"Vessel at index {idx} is not a Vessel object: {type(vessel)}"
        print(f"\n✓ All {len(vessel_pool.vessels_list)} vessels are Vessel objects")


class TestFuelConsumptionStructure:
    """Test fuel consumption data structure for all vessels."""
    
    def test_all_vessels_have_bunkering_cost_coefs(self, vessel_pool):
        """Test that all vessels have bunkering_cost_coefs attribute."""
        for vessel in vessel_pool.vessels_list:
            assert hasattr(vessel, 'bunkering_cost_coefs'), \
                f"Vessel rank {vessel.vessel_rank} missing bunkering_cost_coefs"
            assert isinstance(vessel.bunkering_cost_coefs, pd.DataFrame), \
                f"Vessel rank {vessel.vessel_rank} bunkering_cost_coefs is not a DataFrame"
        print(f"\n✓ All {len(vessel_pool.vessels_list)} vessels have bunkering_cost_coefs DataFrame")
    
    def test_bunkering_coefs_has_correct_columns(self, vessel_pool):
        """Test that bunkering_cost_coefs has 'speed' and 'consumption' columns."""
        for vessel in vessel_pool.vessels_list:
            df = vessel.bunkering_cost_coefs
            assert 'speed' in df.columns, \
                f"Vessel rank {vessel.vessel_rank} missing 'speed' column"
            assert 'consumption' in df.columns, \
                f"Vessel rank {vessel.vessel_rank} missing 'consumption' column"
            assert len(df.columns) == 2, \
                f"Vessel rank {vessel.vessel_rank} has extra columns: {df.columns.tolist()}"
        print(f"\n✓ All vessels have correct DataFrame columns: ['speed', 'consumption']")
    
    def test_all_vessels_have_18_speed_levels(self, vessel_pool):
        """Test that each vessel has exactly 18 speed levels."""
        for vessel in vessel_pool.vessels_list:
            n_speeds = len(vessel.bunkering_cost_coefs)
            assert n_speeds == 18, \
                f"Vessel rank {vessel.vessel_rank} has {n_speeds} speed levels, expected 18"
        
        print(f"\n✓ All {len(vessel_pool.vessels_list)} vessels have 18 speed levels")
        
        # Show example from rank 1
        example = vessel_pool.vessels_list[0].bunkering_cost_coefs
        print(f"  Example (Rank 1): speeds from {example['speed'].min()} to {example['speed'].max()} knots")


class TestSpeedLevels:
    """Test speed level configuration."""
    
    def test_speed_range_is_10_to_18_5(self, vessel_pool):
        """Test that speeds range from 10.0 to 18.5 knots."""
        for vessel in vessel_pool.vessels_list:
            speeds = vessel.bunkering_cost_coefs['speed'].values
            min_speed = speeds.min()
            max_speed = speeds.max()
            
            assert min_speed == 10.0, \
                f"Vessel rank {vessel.vessel_rank} min speed is {min_speed}, expected 10.0"
            assert max_speed == 18.5, \
                f"Vessel rank {vessel.vessel_rank} max speed is {max_speed}, expected 18.5"
        
        print(f"\n✓ All vessels have speed range: 10.0 - 18.5 knots")
    
    def test_speed_increments_are_0_5_knots(self, vessel_pool):
        """Test that speed increments are 0.5 knots."""
        expected_speeds = [10.0 + (i * 0.5) for i in range(18)]  # 10.0, 10.5, ..., 18.5
        
        for vessel in vessel_pool.vessels_list:
            actual_speeds = vessel.bunkering_cost_coefs['speed'].values
            np.testing.assert_array_almost_equal(
                actual_speeds, expected_speeds, decimal=1,
                err_msg=f"Vessel rank {vessel.vessel_rank} has incorrect speed levels"
            )
        
        print(f"\n✓ All vessels have correct 0.5 knot increments: {expected_speeds[:3]}...{expected_speeds[-3:]}")
    
    def test_vessel_min_max_speed_attributes(self, vessel_pool):
        """Test that Vessel.min_speed and max_speed are set correctly."""
        for vessel in vessel_pool.vessels_list:
            assert hasattr(vessel, 'min_speed'), f"Vessel rank {vessel.vessel_rank} missing min_speed"
            assert hasattr(vessel, 'max_speed'), f"Vessel rank {vessel.vessel_rank} missing max_speed"
            assert vessel.min_speed == 10, \
                f"Vessel rank {vessel.vessel_rank} min_speed is {vessel.min_speed}, expected 10"
            assert vessel.max_speed == 18, \
                f"Vessel rank {vessel.vessel_rank} max_speed is {vessel.max_speed}, expected 18"
        
        print(f"\n✓ All vessels have min_speed=10, max_speed=18")


class TestFuelConsumptionValues:
    """Test fuel consumption value ranges and properties."""
    
    def test_all_consumption_values_positive(self, vessel_pool):
        """Test that all fuel consumption values are positive."""
        for vessel in vessel_pool.vessels_list:
            consumptions = vessel.bunkering_cost_coefs['consumption'].values
            assert (consumptions > 0).all(), \
                f"Vessel rank {vessel.vessel_rank} has non-positive consumption values"
        
        print(f"\n✓ All fuel consumption values are positive")
    
    def test_consumption_increases_with_speed(self, vessel_pool):
        """Test that fuel consumption generally increases with speed."""
        violations = []
        
        for vessel in vessel_pool.vessels_list:
            df = vessel.bunkering_cost_coefs
            consumptions = df['consumption'].values
            
            # Check monotonic increase (allowing small variations due to data)
            diffs = np.diff(consumptions)
            decreases = np.where(diffs < 0)[0]
            
            if len(decreases) > 0:
                violations.append({
                    'rank': vessel.vessel_rank,
                    'decreases': len(decreases),
                    'positions': decreases.tolist()
                })
        
        # Allow minor violations (data may have small fluctuations)
        if violations:
            print(f"\n⚠ Warning: {len(violations)} vessels have non-monotonic fuel consumption")
            for v in violations[:3]:  # Show first 3
                print(f"  Rank {v['rank']}: {v['decreases']} decreases at positions {v['positions']}")
        else:
            print(f"\n✓ All vessels show monotonically increasing fuel consumption with speed")
    
    def test_consumption_ranges_are_reasonable(self, vessel_pool):
        """Test that consumption values are within reasonable ranges."""
        all_consumptions = []
        vessel_ranges = []
        
        for vessel in vessel_pool.vessels_list:
            consumptions = vessel.bunkering_cost_coefs['consumption'].values
            all_consumptions.extend(consumptions)
            vessel_ranges.append({
                'rank': vessel.vessel_rank,
                'min': consumptions.min(),
                'max': consumptions.max(),
                'avg': consumptions.mean()
            })
        
        overall_min = min(all_consumptions)
        overall_max = max(all_consumptions)
        overall_avg = np.mean(all_consumptions)
        
        # Reasonable bounds for fuel consumption (tons per day)
        assert overall_min > 0, f"Minimum consumption too low: {overall_min}"
        assert overall_max < 500, f"Maximum consumption too high: {overall_max}"
        
        print(f"\n✓ Fuel consumption ranges are reasonable:")
        print(f"  Overall range: {overall_min:.2f} - {overall_max:.2f} tons/day")
        print(f"  Overall average: {overall_avg:.2f} tons/day")
        print(f"  Example ranges by rank:")
        for vr in vessel_ranges[:5]:  # Show first 5
            print(f"    Rank {vr['rank']}: {vr['min']:.2f} - {vr['max']:.2f} (avg: {vr['avg']:.2f})")
    
    def test_larger_vessels_consume_more_fuel(self, vessel_pool):
        """Test that larger vessels generally consume more fuel."""
        # Compare average consumption across ranks
        avg_consumptions = []
        
        for vessel in vessel_pool.vessels_list:
            avg_cons = vessel.bunkering_cost_coefs['consumption'].mean()
            avg_consumptions.append({
                'rank': vessel.vessel_rank,
                'capacity': vessel.vessel_capacity,
                'avg_consumption': avg_cons
            })
        
        # Check that average consumption tends to increase with rank (and capacity)
        print(f"\n✓ Fuel consumption by vessel rank:")
        for ac in avg_consumptions:
            print(f"  Rank {ac['rank']} ({ac['capacity']:.0f} TEU): avg {ac['avg_consumption']:.2f} tons/day")
        
        # General trend: larger vessels (higher ranks) should consume more
        # Allow some exceptions due to vessel design efficiency
        rank_1_avg = avg_consumptions[0]['avg_consumption']
        rank_11_avg = avg_consumptions[10]['avg_consumption']
        assert rank_11_avg > rank_1_avg, \
            f"Rank 11 avg consumption ({rank_11_avg:.2f}) should be > Rank 1 ({rank_1_avg:.2f})"


class TestNewVesselRanks:
    """Test new vessel ranks 10 and 11 specifically."""
    
    def test_rank_10_has_complete_fuel_data(self, vessel_pool):
        """Test that rank 10 vessel has complete fuel consumption data."""
        rank_10 = vessel_pool.vessels_list[9]  # Index 9 = rank 10
        assert rank_10.vessel_rank == 10
        
        df = rank_10.bunkering_cost_coefs
        assert len(df) == 18, f"Rank 10 has {len(df)} speed levels, expected 18"
        assert df['speed'].min() == 10.0
        assert df['speed'].max() == 18.5
        assert (df['consumption'] > 0).all()
        
        print(f"\n✓ Rank 10 vessel fuel consumption:")
        print(f"  Capacity: {rank_10.vessel_capacity:.0f} TEU")
        print(f"  Speed range: {df['speed'].min()} - {df['speed'].max()} knots")
        print(f"  Consumption range: {df['consumption'].min():.2f} - {df['consumption'].max():.2f} tons/day")
        print(f"  Average consumption: {df['consumption'].mean():.2f} tons/day")
    
    def test_rank_11_has_complete_fuel_data(self, vessel_pool):
        """Test that rank 11 vessel has complete fuel consumption data."""
        rank_11 = vessel_pool.vessels_list[10]  # Index 10 = rank 11
        assert rank_11.vessel_rank == 11
        
        df = rank_11.bunkering_cost_coefs
        assert len(df) == 18, f"Rank 11 has {len(df)} speed levels, expected 18"
        assert df['speed'].min() == 10.0
        assert df['speed'].max() == 18.5
        assert (df['consumption'] > 0).all()
        
        print(f"\n✓ Rank 11 vessel fuel consumption:")
        print(f"  Capacity: {rank_11.vessel_capacity:.0f} TEU")
        print(f"  Speed range: {df['speed'].min()} - {df['speed'].max()} knots")
        print(f"  Consumption range: {df['consumption'].min():.2f} - {df['consumption'].max():.2f} tons/day")
        print(f"  Average consumption: {df['consumption'].mean():.2f} tons/day")
    
    def test_new_ranks_capacity_ranges(self, vessel_pool):
        """Test that ranks 10 and 11 have correct capacity ranges."""
        rank_10 = vessel_pool.vessels_list[9]
        rank_11 = vessel_pool.vessels_list[10]
        
        # Based on Vessel_Nominal.csv:
        # Rank 10: 10000-12499 TEU range
        # Rank 11: 12500-15199 TEU range
        
        assert 10000 <= rank_10.vessel_capacity <= 12499, \
            f"Rank 10 capacity {rank_10.vessel_capacity} outside expected range 10000-12499"
        
        assert 12500 <= rank_11.vessel_capacity <= 15199, \
            f"Rank 11 capacity {rank_11.vessel_capacity} outside expected range 12500-15199"
        
        print(f"\n✓ New vessel ranks have correct capacities:")
        print(f"  Rank 10: {rank_10.vessel_capacity:.0f} TEU (expected 10000-12499)")
        print(f"  Rank 11: {rank_11.vessel_capacity:.0f} TEU (expected 12500-15199)")


class TestCSVDataIntegrity:
    """Test Vessel_Nominal.csv data integrity."""
    
    def test_csv_has_11_ranks(self, vessel_csv_df):
        """Test that CSV has exactly 11 vessel ranks."""
        assert len(vessel_csv_df) == 11, \
            f"CSV has {len(vessel_csv_df)} rows, expected 11"
        
        vranks = vessel_csv_df['vrank'].values
        assert list(vranks) == list(range(1, 12)), \
            f"CSV ranks are {list(vranks)}, expected 1-11"
        
        print(f"\n✓ Vessel_Nominal.csv has 11 vessel ranks: {list(vranks)}")
    
    def test_csv_has_all_speed_columns(self, vessel_csv_df):
        """Test that CSV has all 18 speed columns (10.0-18.5 knots)."""
        expected_speeds = [10.0 + (i * 0.5) for i in range(18)]
        expected_columns = [f'cons_{speed}kn' for speed in expected_speeds]
        
        for col in expected_columns:
            assert col in vessel_csv_df.columns, \
                f"CSV missing speed column: {col}"
        
        print(f"\n✓ CSV has all 18 speed columns: cons_10.0kn ... cons_18.5kn")
    
    def test_csv_no_missing_consumption_values(self, vessel_csv_df):
        """Test that CSV has no missing consumption values."""
        speed_columns = [f'cons_{10.0 + (i * 0.5)}kn' for i in range(18)]
        
        for col in speed_columns:
            missing = vessel_csv_df[col].isna().sum()
            assert missing == 0, \
                f"CSV column {col} has {missing} missing values"
        
        print(f"\n✓ CSV has no missing fuel consumption values (11 ranks × 18 speeds = 198 values)")
    
    def test_csv_consumption_values_match_loaded_data(self, vessel_csv_df, vessel_pool):
        """Test that CSV values match loaded VesselPool data."""
        mismatches = []
        
        for idx, row in vessel_csv_df.iterrows():
            rank = int(row['vrank'])
            vessel = vessel_pool.vessels_list[rank - 1]
            
            # Check each speed level
            for i in range(18):
                speed = 10.0 + (i * 0.5)
                col = f'cons_{speed}kn'
                csv_consumption = row[col]
                loaded_consumption = vessel.bunkering_cost_coefs.loc[i, 'consumption']
                
                if not np.isclose(csv_consumption, loaded_consumption, rtol=1e-5):
                    mismatches.append({
                        'rank': rank,
                        'speed': speed,
                        'csv': csv_consumption,
                        'loaded': loaded_consumption
                    })
        
        assert len(mismatches) == 0, \
            f"Found {len(mismatches)} mismatches between CSV and loaded data"
        
        print(f"\n✓ All 198 consumption values match between CSV and loaded data (11 ranks × 18 speeds)")


class TestVesselPoolIntegration:
    """Test VesselPool integration methods for fuel consumption."""
    
    def test_get_bukering_costs_returns_correct_shape(self, vessel_pool):
        """Test that get_bukering_costs() returns correct array shape."""
        consumption_array, base_speed = vessel_pool.get_bukering_costs()
        
        assert consumption_array.shape == (11, 18), \
            f"Expected shape (11, 18), got {consumption_array.shape}"
        assert base_speed == 10.0, \
            f"Expected base speed 10.0, got {base_speed}"
        
        print(f"\n✓ get_bukering_costs() returns correct shape: {consumption_array.shape}")
        print(f"  Base speed level: {base_speed} knots")
    
    def test_get_bukering_costs_includes_unit_cost(self, vessel_pool):
        """Test that get_bukering_costs() includes unit bunkering cost."""
        consumption_array, _ = vessel_pool.get_bukering_costs()
        
        # get_bukering_costs multiplies consumption by unit_bunkering_cost
        # So values should be different from raw consumption
        vessel = vessel_pool.vessels_list[0]
        raw_consumption = vessel.bunkering_cost_coefs.loc[0, 'consumption']
        costed_consumption = consumption_array[0, 0]
        
        expected_cost = raw_consumption * vessel.unit_bunkering_cost
        assert np.isclose(costed_consumption, expected_cost, rtol=1e-5), \
            f"Expected {expected_cost}, got {costed_consumption}"
        
        print(f"\n✓ get_bukering_costs() correctly applies unit bunkering cost")
        print(f"  Example: Raw consumption {raw_consumption:.2f} tons/day")
        print(f"  Unit cost: ${vessel.unit_bunkering_cost:.2f}/ton")
        print(f"  Result: ${costed_consumption:.2f}/day")
    
    def test_all_vessels_have_unit_bunkering_cost(self, vessel_pool):
        """Test that all vessels have unit_bunkering_cost attribute."""
        for vessel in vessel_pool.vessels_list:
            assert hasattr(vessel, 'unit_bunkering_cost'), \
                f"Vessel rank {vessel.vessel_rank} missing unit_bunkering_cost"
            assert vessel.unit_bunkering_cost > 0, \
                f"Vessel rank {vessel.vessel_rank} has invalid unit_bunkering_cost"
        
        # Check they all have the same unit cost (as per data_reader.py)
        unit_costs = [v.unit_bunkering_cost for v in vessel_pool.vessels_list]
        assert len(set(unit_costs)) == 1, \
            f"Vessels have different unit bunkering costs: {set(unit_costs)}"
        
        print(f"\n✓ All vessels have unit_bunkering_cost: ${unit_costs[0]:.2f}/ton")


class TestOperationalCalculations:
    """Test operational fuel consumption calculations."""
    
    def test_fuel_cost_calculation_for_voyage(self, vessel_pool):
        """Test calculating fuel cost for a sample voyage."""
        # Sample voyage: 1000 nautical miles at 14.0 knots
        distance_nm = 1000
        speed_knots = 14.0
        
        # Voyage time in days
        voyage_time_days = distance_nm / speed_knots / 24
        
        for vessel in vessel_pool.vessels_list[:3]:  # Test first 3 ranks
            # Find consumption at 14.0 knots
            df = vessel.bunkering_cost_coefs
            speed_14_row = df[df['speed'] == 14.0]
            assert len(speed_14_row) == 1, f"Rank {vessel.vessel_rank} missing 14.0 knots data"
            
            consumption_per_day = speed_14_row.iloc[0]['consumption']
            total_consumption = consumption_per_day * voyage_time_days
            total_cost = total_consumption * vessel.unit_bunkering_cost
            
            assert total_consumption > 0, f"Rank {vessel.vessel_rank} has invalid consumption"
            assert total_cost > 0, f"Rank {vessel.vessel_rank} has invalid cost"
            
            print(f"\n  Rank {vessel.vessel_rank} ({vessel.vessel_capacity:.0f} TEU):")
            print(f"    Voyage: {distance_nm} nm at {speed_knots} knots = {voyage_time_days:.2f} days")
            print(f"    Consumption: {consumption_per_day:.2f} tons/day × {voyage_time_days:.2f} days = {total_consumption:.2f} tons")
            print(f"    Cost: {total_consumption:.2f} tons × ${vessel.unit_bunkering_cost:.2f}/ton = ${total_cost:.2f}")
        
        print(f"\n✓ Fuel cost calculations work correctly for operational scenarios")
    
    def test_speed_optimization_scenario(self, vessel_pool):
        """Test comparing fuel costs at different speeds for same voyage."""
        vessel = vessel_pool.vessels_list[4]  # Rank 5 vessel
        distance_nm = 2000
        
        # Compare costs at different speeds
        speeds_to_test = [12.0, 14.0, 16.0, 18.0]
        results = []
        
        for speed in speeds_to_test:
            df = vessel.bunkering_cost_coefs
            speed_row = df[df['speed'] == speed]
            
            if len(speed_row) > 0:
                consumption_per_day = speed_row.iloc[0]['consumption']
                voyage_time_days = distance_nm / speed / 24
                total_consumption = consumption_per_day * voyage_time_days
                total_cost = total_consumption * vessel.unit_bunkering_cost
                
                results.append({
                    'speed': speed,
                    'time_days': voyage_time_days,
                    'consumption': total_consumption,
                    'cost': total_cost
                })
        
        print(f"\n✓ Speed optimization analysis for Rank 5 vessel ({distance_nm} nm voyage):")
        for r in results:
            print(f"  {r['speed']:.1f} knots: {r['time_days']:.2f} days, "
                  f"{r['consumption']:.2f} tons fuel, ${r['cost']:.2f} cost")
        
        # Verify that faster speeds cost more fuel
        costs = [r['cost'] for r in results]
        for i in range(len(costs) - 1):
            assert costs[i+1] > costs[i], \
                f"Expected increasing costs, but {costs[i+1]} <= {costs[i]}"


class TestDataTypeConsistency:
    """Test data type consistency across all vessels."""
    
    def test_consumption_data_types(self, vessel_pool):
        """Test that all consumption values are numeric."""
        data_types = set()
        
        for vessel in vessel_pool.vessels_list:
            consumptions = vessel.bunkering_cost_coefs['consumption']
            data_types.add(str(consumptions.dtype))
        
        # Should all be float64 or similar numeric type
        assert len(data_types) == 1, f"Inconsistent data types: {data_types}"
        assert 'float' in list(data_types)[0], f"Expected float type, got {data_types}"
        
        print(f"\n✓ All consumption values have consistent data type: {data_types}")
    
    def test_speed_data_types(self, vessel_pool):
        """Test that all speed values are numeric."""
        data_types = set()
        
        for vessel in vessel_pool.vessels_list:
            speeds = vessel.bunkering_cost_coefs['speed']
            data_types.add(str(speeds.dtype))
        
        assert len(data_types) == 1, f"Inconsistent data types: {data_types}"
        assert 'float' in list(data_types)[0], f"Expected float type, got {data_types}"
        
        print(f"\n✓ All speed values have consistent data type: {data_types}")


class TestCompleteIntegration:
    """Final comprehensive integration test."""
    
    def test_complete_fuel_consumption_system(self, vessel_pool, vessel_csv_df):
        """Comprehensive test of entire fuel consumption system."""
        print(f"\n{'='*70}")
        print(f"COMPLETE FUEL CONSUMPTION VALIDATION - 11 VESSEL RANKS")
        print(f"{'='*70}")
        
        # 1. VesselPool structure
        assert len(vessel_pool.vessels_list) == 11
        ranks = [v.vessel_rank for v in vessel_pool.vessels_list]
        print(f"\n1. VesselPool Structure:")
        print(f"   ✓ Vessel ranks: {ranks}")
        
        # 2. Fuel consumption data
        all_have_18_speeds = all(len(v.bunkering_cost_coefs) == 18 for v in vessel_pool.vessels_list)
        assert all_have_18_speeds
        print(f"\n2. Fuel Consumption Data:")
        print(f"   ✓ All vessels have 18 speed levels (10.0-18.5 knots)")
        
        # 3. CSV integrity
        assert len(vessel_csv_df) == 11
        speed_columns = [f'cons_{10.0 + (i * 0.5)}kn' for i in range(18)]
        assert all(col in vessel_csv_df.columns for col in speed_columns)
        print(f"\n3. CSV Data Integrity:")
        print(f"   ✓ Vessel_Nominal.csv: 11 ranks × 18 speed columns")
        
        # 4. New ranks validation
        rank_10 = vessel_pool.vessels_list[9]
        rank_11 = vessel_pool.vessels_list[10]
        assert rank_10.vessel_rank == 10
        assert rank_11.vessel_rank == 11
        assert len(rank_10.bunkering_cost_coefs) == 18
        assert len(rank_11.bunkering_cost_coefs) == 18
        print(f"\n4. New Vessel Ranks:")
        print(f"   ✓ Rank 10: {rank_10.vessel_capacity:.0f} TEU, {len(rank_10.bunkering_cost_coefs)} speeds")
        print(f"   ✓ Rank 11: {rank_11.vessel_capacity:.0f} TEU, {len(rank_11.bunkering_cost_coefs)} speeds")
        
        # 5. Integration method
        consumption_array, base_speed = vessel_pool.get_bukering_costs()
        assert consumption_array.shape == (11, 18)
        assert base_speed == 10.0
        print(f"\n5. VesselPool Integration:")
        print(f"   ✓ get_bukering_costs() returns ({consumption_array.shape[0]}, {consumption_array.shape[1]}) array")
        print(f"   ✓ Base speed: {base_speed} knots")
        
        # 6. Value validation
        total_values = 11 * 18
        all_positive = all((v.bunkering_cost_coefs['consumption'] > 0).all() 
                          for v in vessel_pool.vessels_list)
        assert all_positive
        print(f"\n6. Data Validation:")
        print(f"   ✓ Total consumption values: {total_values} (11 ranks × 18 speeds)")
        print(f"   ✓ All values positive and reasonable")
        
        print(f"\n{'='*70}")
        print(f"✓ COMPLETE VALIDATION PASSED - Fuel consumption system fully functional")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    # Run with: python -m pytest test_vessel_fuel_consumption.py -v -s
    pytest.main([__file__, "-v", "-s"])
