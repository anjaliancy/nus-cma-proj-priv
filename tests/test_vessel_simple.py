"""
Simplified test for vessel migration - avoids importing full cma package
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import pandas as pd
from importlib import resources

# Direct test without full imports
def test_vessel_data_loads():
    """Test that vessel CSV can be loaded and has correct structure"""
    import cma.res
    file = resources.files('cma.res').joinpath('input/Vessel_Nominal.csv')
    df = pd.read_csv(file)
    
    print(f"✓ Loaded {len(df)} vessel classes")
    assert len(df) == 11, f"Expected 11 vessel classes, got {len(df)}"
    
    # Check columns exist
    required_cols = ['vrank', 'sizeclass', 'cap_nom', 'cost_charter',
                     'cons_canal', 'cons_port', 'cons_man', 'cons_sea']
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    
    # Check speed columns (16 levels)
    speed_cols = [f'cons_{speed}kn' for speed in 
                  [10.0, 10.5, 11.0, 11.5, 12.0, 12.5, 13.0, 13.5,
                   14.0, 14.5, 15.0, 15.5, 16.0, 16.5, 17.0, 17.5, 18.0, 18.5]]
    for col in speed_cols:
        assert col in df.columns, f"Missing speed column: {col}"
    
    print(f"✓ All required columns present")
    
    # Check vessel ranks are 1-11
    ranks = df['vrank'].tolist()
    assert ranks == list(range(1, 12)), f"Expected ranks 1-11, got {ranks}"
    print(f"✓ Vessel ranks are 1-11")
    
    # Check capacities
    expected_caps = {
        1: 238, 2: 742, 3: 1158, 4: 1705, 5: 2421, 6: 3461,
        7: 4502, 8: 6193, 9: 8835, 10: 10756, 11: 13033
    }
    for _, row in df.iterrows():
        rank = int(row['vrank'])
        cap = int(row['cap_nom'])
        assert cap == expected_caps[rank], \
            f"Rank {rank}: expected capacity {expected_caps[rank]}, got {cap}"
    print(f"✓ All vessel capacities correct")
    
    # Check fuel consumption values are positive and increasing
    for _, row in df.iterrows():
        rank = int(row['vrank'])
        consumptions = [row[col] for col in speed_cols]
        
        # All positive
        assert all(c > 0 for c in consumptions), \
            f"Rank {rank}: found non-positive consumption"
        
        # Increasing
        for i in range(len(consumptions) - 1):
            assert consumptions[i] < consumptions[i+1], \
                f"Rank {rank}: consumption not increasing at index {i}"
    
    print(f"✓ Fuel consumption curves valid (positive, increasing)")
    
    # Check operational fuel components
    for _, row in df.iterrows():
        rank = int(row['vrank'])
        assert row['cons_canal'] > 0, f"Rank {rank}: cons_canal not positive"
        assert row['cons_port'] > 0, f"Rank {rank}: cons_port not positive"
        assert row['cons_man'] > 0, f"Rank {rank}: cons_man not positive"
        assert row['cons_sea'] > 0, f"Rank {rank}: cons_sea not positive"
    
    print(f"✓ Operational fuel components present and positive")
    
    print("\n" + "="*60)
    print("ALL VESSEL DATA VALIDATION TESTS PASSED ✓")
    print("="*60)
    return True

if __name__ == '__main__':
    try:
        test_vessel_data_loads()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
