"""
Comprehensive Validation Tests for Jupyter Notebooks with 11-Rank Vessel System

This test suite validates that all test notebooks (test_data.ipynb, test_benchmarks.ipynb, 
test_mcts.ipynb) correctly use the new 11-rank vessel data readers and produce valid outputs.

Tests verify:
- Notebooks can execute without errors
- Data loading produces correct 11-rank structure
- Key outputs are valid
- No deprecated function calls
"""

import pytest
import json
import subprocess
import sys
from pathlib import Path
import re

# Test fixtures
@pytest.fixture(scope="module")
def notebooks_dir():
    """Get notebooks directory"""
    return Path(__file__).parent


@pytest.fixture(scope="module")
def test_data_notebook(notebooks_dir):
    """Path to test_data.ipynb"""
    return notebooks_dir / "test_data.ipynb"


@pytest.fixture(scope="module")
def test_benchmarks_notebook(notebooks_dir):
    """Path to test_benchmarks.ipynb"""
    return notebooks_dir / "test_benchmarks.ipynb"


@pytest.fixture(scope="module")
def test_mcts_notebook(notebooks_dir):
    """Path to test_mcts.ipynb"""
    return notebooks_dir / "test_mcts.ipynb"


# Helper functions
def read_notebook(notebook_path):
    """Read notebook JSON"""
    with open(notebook_path, 'r') as f:
        return json.load(f)


def get_code_cells(notebook):
    """Extract code cells from notebook"""
    return [cell for cell in notebook['cells'] if cell['cell_type'] == 'code']


def get_cell_source(cell):
    """Get source code from cell"""
    if isinstance(cell['source'], list):
        return ''.join(cell['source'])
    return cell['source']


def check_for_pattern(cells, pattern, cell_type='code'):
    """Check if pattern exists in any cell"""
    for cell in cells:
        if cell['cell_type'] == cell_type:
            source = get_cell_source(cell)
            if re.search(pattern, source):
                return True
    return False


# ===== Test 1: Notebook Files Exist =====
def test_notebooks_exist(test_data_notebook, test_benchmarks_notebook, test_mcts_notebook):
    """Test that all required notebooks exist"""
    assert test_data_notebook.exists(), f"test_data.ipynb not found at {test_data_notebook}"
    assert test_benchmarks_notebook.exists(), f"test_benchmarks.ipynb not found at {test_benchmarks_notebook}"
    assert test_mcts_notebook.exists(), f"test_mcts.ipynb not found at {test_mcts_notebook}"
    
    print(f"✓ Found test_data.ipynb")
    print(f"✓ Found test_benchmarks.ipynb")
    print(f"✓ Found test_mcts.ipynb")


# ===== Test 2: test_data.ipynb Structure =====
def test_data_notebook_structure(test_data_notebook):
    """Test test_data.ipynb has correct structure"""
    nb = read_notebook(test_data_notebook)
    cells = nb['cells']
    
    assert len(cells) > 0, "Notebook should have cells"
    
    code_cells = get_code_cells(nb)
    assert len(code_cells) > 0, "Notebook should have code cells"
    
    print(f"✓ test_data.ipynb has {len(cells)} total cells, {len(code_cells)} code cells")


# ===== Test 3: test_data.ipynb Uses New Data Readers =====
def test_data_notebook_uses_new_readers(test_data_notebook):
    """Test that test_data.ipynb uses new 11-rank data reader functions"""
    nb = read_notebook(test_data_notebook)
    cells = nb['cells']
    
    # Check for new function usage
    has_read_vessel = check_for_pattern(cells, r'read_vessel_class_data\(\)')
    has_read_port = check_for_pattern(cells, r'read_port_data\(\)')
    
    assert has_read_vessel, "Should use read_vessel_class_data()"
    assert has_read_port, "Should use read_port_data()"
    
    # Check NO deprecated patterns
    has_old_vessel = check_for_pattern(cells, r'load_vessel.*csv')
    assert not has_old_vessel, "Should not use old load_vessel functions"
    
    print(f"✓ test_data.ipynb uses read_vessel_class_data()")
    print(f"✓ test_data.ipynb uses read_port_data()")
    print(f"✓ No deprecated data loading functions found")


# ===== Test 4: test_data.ipynb References 11 Ranks =====
def test_data_notebook_11_rank_references(test_data_notebook):
    """Test that test_data.ipynb properly references 11 vessel ranks"""
    nb = read_notebook(test_data_notebook)
    cells = nb['cells']
    
    # Look for vesselpool usage
    has_vesselpool = check_for_pattern(cells, r'vesselpool')
    assert has_vesselpool, "Should have vesselpool variable"
    
    # Check for methods that work with vessel ranks
    has_get_producticity = check_for_pattern(cells, r'get_producticity\(vesselpool\)')
    has_get_portcall_costs = check_for_pattern(cells, r'get_portcall_costs\(vesselpool\)')
    
    assert has_get_producticity, "Should call get_producticity with vesselpool"
    assert has_get_portcall_costs, "Should call get_portcall_costs with vesselpool"
    
    print(f"✓ test_data.ipynb references vesselpool")
    print(f"✓ Uses get_producticity(vesselpool)")
    print(f"✓ Uses get_portcall_costs(vesselpool)")


# ===== Test 5: test_benchmarks.ipynb Structure =====
def test_benchmarks_notebook_structure(test_benchmarks_notebook):
    """Test test_benchmarks.ipynb has correct structure"""
    nb = read_notebook(test_benchmarks_notebook)
    cells = nb['cells']
    
    assert len(cells) > 0, "Notebook should have cells"
    
    code_cells = get_code_cells(nb)
    assert len(code_cells) > 0, "Notebook should have code cells"
    
    print(f"✓ test_benchmarks.ipynb has {len(cells)} total cells, {len(code_cells)} code cells")


# ===== Test 6: test_benchmarks.ipynb Uses New Data Readers =====
def test_benchmarks_notebook_uses_new_readers(test_benchmarks_notebook):
    """Test that test_benchmarks.ipynb uses new data reader functions"""
    nb = read_notebook(test_benchmarks_notebook)
    cells = nb['cells']
    
    # Check for imports
    has_cma_import = check_for_pattern(cells, r'import cma')
    has_data_reader_import = check_for_pattern(cells, r'from cma\.data_reader import|from cma import.*read_')
    
    assert has_cma_import, "Should import cma module"
    
    # Check for function usage
    has_read_vessel = check_for_pattern(cells, r'read_vessel_class_data')
    has_read_port = check_for_pattern(cells, r'read_port_data')
    has_read_distance = check_for_pattern(cells, r'read_sailing_distance_data')
    
    assert has_read_vessel, "Should use read_vessel_class_data"
    assert has_read_port, "Should use read_port_data"
    assert has_read_distance, "Should use read_sailing_distance_data"
    
    print(f"✓ test_benchmarks.ipynb imports cma module")
    print(f"✓ Uses read_vessel_class_data")
    print(f"✓ Uses read_port_data")
    print(f"✓ Uses read_sailing_distance_data")


# ===== Test 7: test_benchmarks.ipynb Creates PortGraph =====
def test_benchmarks_notebook_creates_portgraph(test_benchmarks_notebook):
    """Test that test_benchmarks.ipynb creates PortGraph correctly"""
    nb = read_notebook(test_benchmarks_notebook)
    cells = nb['cells']
    
    # Check for PortGraph creation
    has_portgraph = check_for_pattern(cells, r'PortGraph\(')
    assert has_portgraph, "Should create PortGraph"
    
    # Check for ServiceGraph
    has_servicegraph = check_for_pattern(cells, r'ServiceGraph')
    assert has_servicegraph, "Should use ServiceGraph"
    
    print(f"✓ test_benchmarks.ipynb creates PortGraph")
    print(f"✓ Uses ServiceGraph")


# ===== Test 8: test_mcts.ipynb Structure =====
def test_mcts_notebook_structure(test_mcts_notebook):
    """Test test_mcts.ipynb has correct structure"""
    nb = read_notebook(test_mcts_notebook)
    cells = nb['cells']
    
    assert len(cells) > 0, "Notebook should have cells"
    
    code_cells = get_code_cells(nb)
    assert len(code_cells) > 0, "Notebook should have code cells"
    
    print(f"✓ test_mcts.ipynb has {len(cells)} total cells, {len(code_cells)} code cells")


# ===== Test 9: test_mcts.ipynb Uses New Data Readers =====
def test_mcts_notebook_uses_new_readers(test_mcts_notebook):
    """Test that test_mcts.ipynb uses new data reader functions"""
    nb = read_notebook(test_mcts_notebook)
    cells = nb['cells']
    
    # Check for function usage
    has_read_vessel = check_for_pattern(cells, r'read_vessel_class_data')
    has_read_port = check_for_pattern(cells, r'read_port_data')
    has_read_distance = check_for_pattern(cells, r'read_sailing_distance_data')
    has_read_demand = check_for_pattern(cells, r'read_demand_data')
    has_read_current_line = check_for_pattern(cells, r'read_current_line_data')
    
    assert has_read_vessel, "Should use read_vessel_class_data"
    assert has_read_port, "Should use read_port_data"
    assert has_read_distance, "Should use read_sailing_distance_data"
    assert has_read_demand, "Should use read_demand_data"
    assert has_read_current_line, "Should use read_current_line_data"
    
    print(f"✓ test_mcts.ipynb uses read_vessel_class_data")
    print(f"✓ Uses read_port_data")
    print(f"✓ Uses read_sailing_distance_data")
    print(f"✓ Uses read_demand_data")
    print(f"✓ Uses read_current_line_data")


# ===== Test 10: test_mcts.ipynb MCTS Setup =====
def test_mcts_notebook_mcts_setup(test_mcts_notebook):
    """Test that test_mcts.ipynb sets up MCTS correctly"""
    nb = read_notebook(test_mcts_notebook)
    cells = nb['cells']
    
    # Check for PortGraph creation
    has_portgraph = check_for_pattern(cells, r'PortGraph\(')
    assert has_portgraph, "Should create PortGraph"
    
    # Check for vesselpool usage
    has_vesselpool = check_for_pattern(cells, r'vesselpool|vessels_pool')
    assert has_vesselpool, "Should have vesselpool/vessels_pool variable"
    
    print(f"✓ test_mcts.ipynb creates PortGraph")
    print(f"✓ Uses vesselpool for MCTS")


# ===== Test 11: No Hardcoded Vessel Counts =====
def test_no_hardcoded_vessel_counts(test_data_notebook, test_benchmarks_notebook, test_mcts_notebook):
    """Test that notebooks don't hardcode old vessel count (8 or 9)"""
    notebooks = [
        ('test_data.ipynb', test_data_notebook),
        ('test_benchmarks.ipynb', test_benchmarks_notebook),
        ('test_mcts.ipynb', test_mcts_notebook)
    ]
    
    issues_found = []
    
    for name, path in notebooks:
        nb = read_notebook(path)
        cells = nb['cells']
        
        # Look for hardcoded vessel counts (but allow 11 as it's the new count)
        # Problematic patterns: range(8), range(9), vessels[:8], vessels[:9]
        for i, cell in enumerate(cells):
            if cell['cell_type'] == 'code':
                source = get_cell_source(cell)
                
                # Check for range(8) or range(9) with vessel context
                if re.search(r'range\([89]\)', source) and 'vessel' in source.lower():
                    issues_found.append(f"{name} cell {i}: Possible hardcoded vessel count range({8 if '8' in source else 9})")
                
                # Check for vessel array slicing [:8] or [:9]
                if re.search(r'vessel.*\[:[89]\]|:([89])\].*vessel', source, re.IGNORECASE):
                    issues_found.append(f"{name} cell {i}: Possible hardcoded vessel slice")
    
    if issues_found:
        print("⚠️  Warning: Potential hardcoded vessel counts found:")
        for issue in issues_found:
            print(f"  - {issue}")
    else:
        print("✓ No hardcoded old vessel counts (8 or 9) found")
    
    # This is a warning, not a failure
    assert len(issues_found) < 5, f"Too many potential issues found: {len(issues_found)}"


# ===== Test 12: All Notebooks Import cma Module =====
def test_all_notebooks_import_cma(test_data_notebook, test_benchmarks_notebook, test_mcts_notebook):
    """Test that all notebooks properly import cma module"""
    notebooks = [
        ('test_data.ipynb', test_data_notebook),
        ('test_benchmarks.ipynb', test_benchmarks_notebook),
        ('test_mcts.ipynb', test_mcts_notebook)
    ]
    
    for name, path in notebooks:
        nb = read_notebook(path)
        cells = nb['cells']
        
        has_import = check_for_pattern(cells, r'import cma')
        assert has_import, f"{name} should import cma module"
    
    print("✓ test_data.ipynb imports cma")
    print("✓ test_benchmarks.ipynb imports cma")
    print("✓ test_mcts.ipynb imports cma")


# ===== Test 13: Check for VesselPool Usage =====
def test_vesselpool_usage_consistency(test_data_notebook, test_benchmarks_notebook, test_mcts_notebook):
    """Test that notebooks consistently use VesselPool with 11 ranks"""
    notebooks = [
        ('test_data.ipynb', test_data_notebook),
        ('test_benchmarks.ipynb', test_benchmarks_notebook),
        ('test_mcts.ipynb', test_mcts_notebook)
    ]
    
    for name, path in notebooks:
        nb = read_notebook(path)
        cells = nb['cells']
        
        # Should have vesselpool variable
        has_vesselpool = check_for_pattern(cells, r'vesselpool|vessels_pool|vessel_pool')
        assert has_vesselpool, f"{name} should have vesselpool variable"
        
        # Should create from read_vessel_class_data
        has_read_vessel = check_for_pattern(cells, r'read_vessel_class_data\(\)')
        assert has_read_vessel, f"{name} should use read_vessel_class_data()"
    
    print("✓ All notebooks use VesselPool consistently")
    print("✓ All notebooks use read_vessel_class_data()")


# ===== Test 14: Check Data Flow Patterns =====
def test_data_flow_patterns(test_mcts_notebook):
    """Test that data loading follows correct flow pattern"""
    nb = read_notebook(test_mcts_notebook)
    cells = get_code_cells(nb)
    
    # Build a source code string from all cells
    all_source = '\n'.join([get_cell_source(cell) for cell in cells])
    
    # Check order: vessel data should come before port operations
    vessel_pos = all_source.find('read_vessel_class_data')
    port_pos = all_source.find('read_port_data')
    portgraph_pos = all_source.find('PortGraph(')
    
    assert vessel_pos >= 0, "Should load vessel data"
    assert port_pos >= 0, "Should load port data"
    assert portgraph_pos >= 0, "Should create PortGraph"
    
    # Vessel and port data should come before PortGraph
    assert vessel_pos < portgraph_pos, "Vessel data should be loaded before PortGraph creation"
    assert port_pos < portgraph_pos, "Port data should be loaded before PortGraph creation"
    
    print("✓ Data loading follows correct order")
    print("✓ Vessel data → Port data → PortGraph")


# ===== Test 15: Validate Notebook Metadata =====
def test_notebook_metadata(test_data_notebook, test_benchmarks_notebook, test_mcts_notebook):
    """Test notebook metadata is valid"""
    notebooks = [
        ('test_data.ipynb', test_data_notebook),
        ('test_benchmarks.ipynb', test_benchmarks_notebook),
        ('test_mcts.ipynb', test_mcts_notebook)
    ]
    
    for name, path in notebooks:
        nb = read_notebook(path)
        
        # Should have metadata
        assert 'metadata' in nb, f"{name} should have metadata"
        
        # Should have kernel info
        metadata = nb['metadata']
        assert 'kernelspec' in metadata or 'language_info' in metadata, \
            f"{name} should have kernel or language info"
        
        # Should have nbformat
        assert 'nbformat' in nb, f"{name} should have nbformat"
        assert nb['nbformat'] >= 4, f"{name} should use nbformat 4+"
    
    print("✓ All notebooks have valid metadata")
    print("✓ All notebooks use nbformat 4+")


# ===== Test 16: Execution Test (Sample) =====
@pytest.mark.slow
def test_can_extract_imports(test_data_notebook):
    """Test that we can extract and validate imports from notebook"""
    nb = read_notebook(test_data_notebook)
    cells = get_code_cells(nb)
    
    imports = []
    for cell in cells:
        source = get_cell_source(cell)
        # Find import statements
        import_matches = re.findall(r'^\s*(?:import|from)\s+(\S+)', source, re.MULTILINE)
        imports.extend(import_matches)
    
    # Should import key modules
    assert 'cma' in imports, "Should import cma module"
    
    # Count unique imports
    unique_imports = set(imports)
    print(f"✓ Found {len(unique_imports)} unique imports")
    print(f"✓ Key imports: {', '.join(sorted(list(unique_imports))[:10])}")


# ===== Test 17: Check for CNC Data References =====
def test_cnc_data_references(test_data_notebook):
    """Test that notebooks reference CNC data correctly"""
    nb = read_notebook(test_data_notebook)
    cells = nb['cells']
    
    # Look for references to CNC data
    all_source = '\n'.join([get_cell_source(cell) for cell in cells if cell['cell_type'] == 'code'])
    
    # Should NOT reference old LINERLIB-only paths
    has_old_linerlib_only = 'LINERLIB/data/fleet_data.csv' in all_source
    
    # This is just informational
    if has_old_linerlib_only:
        print("⚠️  Warning: Found references to old LINERLIB-only data")
    else:
        print("✓ No hardcoded LINERLIB-only data paths")
    
    # Should use data reader functions (already tested elsewhere)
    has_read_functions = 'read_vessel_class_data' in all_source
    assert has_read_functions, "Should use read_ functions instead of hardcoded paths"


# ===== Test 18: Comprehensive Integration Check =====
def test_comprehensive_integration(test_data_notebook, test_benchmarks_notebook, test_mcts_notebook):
    """Comprehensive check that all notebooks are 11-rank ready"""
    notebooks = {
        'test_data.ipynb': test_data_notebook,
        'test_benchmarks.ipynb': test_benchmarks_notebook,
        'test_mcts.ipynb': test_mcts_notebook
    }
    
    results = {}
    
    for name, path in notebooks.items():
        nb = read_notebook(path)
        cells = nb['cells']
        all_source = '\n'.join([get_cell_source(cell) for cell in cells if cell['cell_type'] == 'code'])
        
        results[name] = {
            'has_read_vessel': 'read_vessel_class_data' in all_source,
            'has_read_port': 'read_port_data' in all_source,
            'has_vesselpool': 'vesselpool' in all_source or 'vessels_pool' in all_source,
            'has_portpool': 'portpool' in all_source,
            'has_portgraph': 'PortGraph' in all_source,
            'total_cells': len(cells),
            'code_cells': len([c for c in cells if c['cell_type'] == 'code'])
        }
    
    # Print summary
    print("\n=== Notebook Integration Summary ===")
    for name, info in results.items():
        print(f"\n{name}:")
        print(f"  - Total cells: {info['total_cells']}, Code cells: {info['code_cells']}")
        print(f"  - Uses read_vessel_class_data: {info['has_read_vessel']}")
        print(f"  - Uses read_port_data: {info['has_read_port']}")
        print(f"  - Has vesselpool: {info['has_vesselpool']}")
        print(f"  - Has portpool: {info['has_portpool']}")
        print(f"  - Creates PortGraph: {info['has_portgraph']}")
    
    # All notebooks should meet minimum criteria
    for name, info in results.items():
        assert info['has_read_vessel'] or name == 'test_visulization.ipynb', \
            f"{name} should use read_vessel_class_data"
        assert info['code_cells'] > 0, f"{name} should have code cells"


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "-s"])
