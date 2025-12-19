"""
Standalone test for vessel CSV data - no cma package imports
"""
import pandas as pd
import os

def test_vessel_csv_directly():
    """Test vessel CSV file directly without importing cma package"""
    # Direct path to CSV
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'cma', 'res', 'input', 'Vessel_Nominal.csv')
    
    print(f"Loading: {csv_path}")
    assert os.path.exists(csv_path), f"CSV file not found: {csv_path}"
    
    df = pd.read_csv(csv_path)
    df = df.rename(columns=lambda x: x.strip())
    
    print(f"✓ Loaded {len(df)} vessel classes")
    assert len(df) == 11, f"Expected 11 vessel classes, got {len(df)}"
    
    # Check columns exist
    required_cols = ['vrank', 'sizeclass', 'cap_nom', 'cost_charter',
                     'cons_canal', 'cons_port', 'cons_man', 'cons_sea']
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    
    # Check speed columns (16 levels)
    speed_cols = [f'cons_{speed}kn' for speed in 
                  ['10.0', '10.5', '11.0', '11.5', '12.0', '12.5', '13.0', '13.5',
                   '14.0', '14.5', '15.0', '15.5', '16.0', '16.5', '17.0', '17.5', '18.0', '18.5']]
    for col in speed_cols:
        assert col in df.columns, f"Missing speed column: {col}"
    
    print(f"✓ All {len(required_cols) + len(speed_cols)} required columns present")
    
    # Check vessel ranks are 1-11
    ranks = df['vrank'].tolist()
    assert ranks == list(range(1, 12)), f"Expected ranks 1-11, got {ranks}"
    print(f"✓ Vessel ranks are consecutive 1-11")
    
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
    print(f"✓ All vessel capacities match expected values")
    
    # Check size classes
    expected_size_classes = [
        "100 - 499", "500 - 999", "1000 - 1499", "1500 - 1999",
        "2000 - 2999", "3000 - 3999", "4000 - 5099", "5100 - 7499",
        "7500 - 9999", "10000 - 12499", "12500 - 15199"
    ]
    for idx, row in df.iterrows():
        assert row['sizeclass'] == expected_size_classes[idx], \
            f"Rank {idx+1}: size class mismatch"
    print(f"✓ All size classes correct")
    
    # Check fuel consumption values are positive and increasing
    for _, row in df.iterrows():
        rank = int(row['vrank'])
        consumptions = [row[col] for col in speed_cols]
        
        # All positive
        assert all(c > 0 for c in consumptions), \
            f"Rank {rank}: found non-positive consumption"
        
        # Increasing (fuel consumption should increase with speed)
        for i in range(len(consumptions) - 1):
            assert consumptions[i] < consumptions[i+1], \
                f"Rank {rank}: consumption not increasing from {speed_cols[i]} to {speed_cols[i+1]}"
    
    print(f"✓ All fuel consumption curves valid (positive & strictly increasing)")
    
    # Check operational fuel components
    for _, row in df.iterrows():
        rank = int(row['vrank'])
        assert row['cons_canal'] > 0, f"Rank {rank}: cons_canal not positive"
        assert row['cons_port'] > 0, f"Rank {rank}: cons_port not positive"
        assert row['cons_man'] > 0, f"Rank {rank}: cons_man not positive"
        assert row['cons_sea'] > 0, f"Rank {rank}: cons_sea not positive"
    
    print(f"✓ All operational fuel components (canal/port/man/sea) are positive")
    
    # Check chartering costs are reasonable
    for _, row in df.iterrows():
        rank = int(row['vrank'])
        cost = row['cost_charter']
        assert cost > 0, f"Rank {rank}: chartering cost not positive"
        assert cost < 100000, f"Rank {rank}: chartering cost unusually high ({cost})"
    print(f"✓ All chartering costs are positive and reasonable")
    
    # Check chartering cost generally increases with size
    costs = df['cost_charter'].tolist()
    avg_small = sum(costs[0:4]) / 4
    avg_large = sum(costs[7:11]) / 4
    assert avg_large > avg_small, \
        f"Large vessels should cost more than small (avg_large={avg_large}, avg_small={avg_small})"
    print(f"✓ Chartering costs increase with vessel size (avg small={avg_small:.0f}, avg large={avg_large:.0f})")
    
    print("\n" + "="*70)
    print(" ALL VESSEL CSV DATA VALIDATION TESTS PASSED ✓")
    print("="*70)
    print(f"\nSummary:")
    print(f"  - 11 vessel classes (ranks 1-11)")
    print(f"  - 16 fuel consumption levels per vessel (10.0-18.5 kn, 0.5 kn steps)")
    print(f"  - 4 operational fuel components per vessel")
    print(f"  - Capacities: {min(expected_caps.values())} - {max(expected_caps.values())} TEU")
    print(f"  - All data valid and ready for migration")
    print("="*70)
    
    return True

if __name__ == '__main__':
    import sys
    try:
        test_vessel_csv_directly()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
