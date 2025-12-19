"""
Standalone test for port CSV data - no cma package imports
Validates the input/Port_Dataset.csv file structure and content
"""
import pandas as pd
import os

def test_port_csv_directly():
    """Test port CSV file directly without importing cma package"""
    # Direct path to CSV
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'cma', 'res', 'input', 'Port_Dataset.csv')
    
    print(f"Loading: {csv_path}")
    assert os.path.exists(csv_path), f"CSV file not found: {csv_path}"
    
    df = pd.read_csv(csv_path)
    df = df.rename(columns=lambda x: x.strip())
    
    print(f"✓ Loaded {len(df)} ports")
    assert len(df) == 182, f"Expected 182 ports, got {len(df)}"
    
    # Check required columns exist
    required_cols = ['PortID', 'Longitude', 'Latitude', 'MaxDraft', 
                     'TranshipmentCost', 'StorageCost', 'DaysFree',
                     'TranshipmentCapacity', 'MaxDailyPortCall']
    for col in required_cols:
        assert col in df.columns, f"Missing column: {col}"
    
    print(f"✓ All {len(required_cols)} required columns present")
    
    # Check for no missing port IDs
    assert df['PortID'].notna().all(), "Found missing port IDs"
    assert df['PortID'].nunique() == len(df), "Found duplicate port IDs"
    print(f"✓ All port IDs unique and non-null")
    
    # Check port ID format (should be UN/LOCODE format: 2-letter country + 3-letter location)
    port_ids = df['PortID'].tolist()
    for pid in port_ids:
        assert isinstance(pid, str) and len(pid) == 5, \
            f"Invalid port ID format: {pid} (expected 5-char UN/LOCODE)"
    print(f"✓ All port IDs follow UN/LOCODE format (5 characters)")
    
    # Check longitude range (-180 to 180)
    assert df['Longitude'].between(-180, 180).all(), \
        "Found invalid longitude values"
    print(f"✓ All longitudes in valid range (-180 to 180)")
    
    # Check latitude range (-90 to 90)
    assert df['Latitude'].between(-90, 90).all(), \
        "Found invalid latitude values"
    print(f"✓ All latitudes in valid range (-90 to 90)")
    
    # Check max draft is positive
    assert (df['MaxDraft'] > 0).all(), "Found non-positive max draft values"
    print(f"✓ All max draft values positive")
    
    # Check transhipment cost (note: 5000 is dummy value for no transshipment)
    assert (df['TranshipmentCost'] >= 0).all(), \
        "Found negative transhipment costs"
    dummy_transship = (df['TranshipmentCost'] == 5000).sum()
    print(f"✓ All transhipment costs non-negative ({dummy_transship} ports with dummy value 5000)")
    
    # Check storage cost (note: 1000000 is dummy value for no storage)
    assert (df['StorageCost'] >= 0).all(), "Found negative storage costs"
    dummy_storage = (df['StorageCost'] == 1000000).sum()
    print(f"✓ All storage costs non-negative ({dummy_storage} ports with dummy value 1000000)")
    
    # Check days free
    assert (df['DaysFree'] >= 0).all(), "Found negative days free values"
    print(f"✓ All days free values non-negative")
    
    # Check transhipment capacity
    assert df['TranshipmentCapacity'].notna().all(), \
        "Found missing transhipment capacity values"
    print(f"✓ All transhipment capacity values present")
    
    # Check max daily port call
    assert (df['MaxDailyPortCall'] > 0).all(), \
        "Found non-positive max daily port call values"
    max_calls = df['MaxDailyPortCall'].max()
    min_calls = df['MaxDailyPortCall'].min()
    print(f"✓ All max daily port call values positive (range: {min_calls}-{max_calls})")
    
    # Geographic distribution check
    asia_pacific = df[df['Longitude'].between(100, 180)].shape[0]
    europe_africa = df[df['Longitude'].between(-20, 50)].shape[0]
    americas = df[(df['Longitude'] < -20) | (df['Longitude'] > -180)].shape[0]
    print(f"\nGeographic distribution:")
    print(f"  - Asia-Pacific region: {asia_pacific} ports")
    print(f"  - Europe-Africa region: {europe_africa} ports")
    print(f"  - Americas region: {americas} ports")
    
    # Sample some well-known ports
    known_ports = {
        'SGSIN': 'Singapore',
        'HKHKG': 'Hong Kong',
        'USNYC': 'New York',
        'NLRTM': 'Rotterdam',
        'CNSHA': 'Shanghai'
    }
    found_ports = []
    for port_id, port_name in known_ports.items():
        if port_id in port_ids:
            found_ports.append(port_name)
    print(f"\nMajor ports found: {', '.join(found_ports)}")
    
    print("\n" + "="*70)
    print(" ALL PORT CSV DATA VALIDATION TESTS PASSED ✓")
    print("="*70)
    print(f"\nSummary:")
    print(f"  - 182 ports loaded from CSV")
    print(f"  - All required columns present")
    print(f"  - All port IDs valid UN/LOCODE format")
    print(f"  - All geographic coordinates valid")
    print(f"  - All cost and capacity values valid")
    print(f"  - Ready for migration from Excel to CSV")
    print("="*70)
    
    return True

if __name__ == '__main__':
    import sys
    try:
        test_port_csv_directly()
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
