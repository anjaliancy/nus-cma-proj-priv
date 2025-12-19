"""
Test suite for verifying system can start from existing network

Tests that the system can:
1. Load existing service lines from proforma data
2. Initialize ServiceGraph from existing lines
3. Use existing network as starting point for optimization
"""

import unittest
import sys
from pathlib import Path
import pandas as pd

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_port_data, read_vessel_class_data
from cma.serviceline import ServiceLine
from cma.servicegraph import ServiceGraph


class TestNetworkInitialization(unittest.TestCase):
    """Test starting from existing network"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.vesselpool = read_vessel_class_data()
    
    def test_proforma_file_exists(self):
        """Test that proforma data file exists"""
        proforma_path = Path(__file__).parent.parent / 'src' / 'cma' / 'res' / 'input' / 'proforma_CNC.csv'
        self.assertTrue(proforma_path.exists(), f"Proforma file not found: {proforma_path}")
    
    def test_load_proforma_data(self):
        """Test loading existing network from proforma"""
        proforma_path = Path(__file__).parent.parent / 'src' / 'cma' / 'res' / 'input' / 'proforma_CNC.csv'
        
        # Load proforma
        df = pd.read_csv(proforma_path)
        
        # Should have data
        self.assertGreater(len(df), 0, "Proforma should contain service lines")
        
        # Should have expected columns
        required_cols = ['linename', 'portid', 'vrank']
        for col in required_cols:
            self.assertIn(col, df.columns, f"Missing column: {col}")
        
        # Should have multiple services
        n_services = df['linename'].nunique()
        self.assertGreater(n_services, 20, f"Expected >20 services, got {n_services}")
    
    def test_create_service_line_from_proforma_ports(self):
        """Test creating ServiceLine from proforma port rotation"""
        # Get sample port rotation from proforma format
        # Example: "CNSHA,CNNGB,SGSIN,HKHKG"
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG']
        
        # Get Port objects
        ports = []
        for port_id in port_ids:
            if self.portpool.has_port_by_id(port_id):
                ports.append(self.portpool.get_port(port_id))
        
        if len(ports) >= 3:
            # Create service line
            line = ServiceLine("ProformaTest", ports, _test=True)
            
            # Should be valid
            self.assertTrue(line.check_valid())
            
            # Should have correct number of ports
            self.assertEqual(line.number_of_port(), len(ports))
    
    def test_create_servicegraph_from_existing_lines(self):
        """Test initializing ServiceGraph from existing service lines"""
        # Create multiple service lines
        port_ids_1 = ['CNSHA', 'CNNGB', 'SGSIN']
        port_ids_2 = ['HKHKG', 'JPYOK', 'CNTAO']
        
        ports_1 = [self.portpool.get_port(pid) for pid in port_ids_1 
                   if self.portpool.has_port_by_id(pid)]
        ports_2 = [self.portpool.get_port(pid) for pid in port_ids_2 
                   if self.portpool.has_port_by_id(pid)]
        
        if len(ports_1) >= 3 and len(ports_2) >= 3:
            line1 = ServiceLine("Line1", ports_1, _test=True)
            line2 = ServiceLine("Line2", ports_2, _test=True)
            
            # Create ServiceGraph
            service_graph = ServiceGraph([line1, line2])
            
            # Should contain both lines
            lines = service_graph.tolist_serviceLine()
            self.assertEqual(len(lines), 2)
            
            # Lines should be accessible
            self.assertIsNotNone(lines[0])
            self.assertIsNotNone(lines[1])
    
    def test_servicegraph_initialization_empty(self):
        """Test ServiceGraph can be initialized with empty list"""
        # Should be able to create empty graph
        service_graph = ServiceGraph([])
        
        # Should have zero lines
        self.assertEqual(len(service_graph.tolist_serviceLine()), 0)
    
    def test_servicegraph_initialization_single_line(self):
        """Test ServiceGraph with single line"""
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG']
        ports = [self.portpool.get_port(pid) for pid in port_ids 
                 if self.portpool.has_port_by_id(pid)]
        
        if len(ports) >= 3:
            line = ServiceLine("SingleLine", ports, _test=True)
            service_graph = ServiceGraph([line])
            
            # Should have exactly one line
            self.assertEqual(len(service_graph.tolist_serviceLine()), 1)
    
    def test_servicegraph_preserves_line_properties(self):
        """Test that ServiceGraph preserves line properties"""
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG']
        ports = [self.portpool.get_port(pid) for pid in port_ids 
                 if self.portpool.has_port_by_id(pid)]
        
        if len(ports) >= 3:
            original_line = ServiceLine("TestLine", ports, _test=True)
            service_graph = ServiceGraph([original_line])
            
            # Get line back from graph
            retrieved_lines = service_graph.tolist_serviceLine()
            retrieved_line = retrieved_lines[0]
            
            # Should have same number of ports
            self.assertEqual(
                retrieved_line.number_of_port(),
                original_line.number_of_port()
            )
            
            # Should have same port sequence
            original_ports = original_line.tolist_port()
            retrieved_ports = retrieved_line.tolist_port()
            
            for i in range(len(original_ports)):
                self.assertEqual(
                    original_ports[i].get_id(),
                    retrieved_ports[i].get_id()
                )
    
    def test_network_ready_for_optimization(self):
        """Test that initialized network is ready for optimization"""
        # Create simple network
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN']
        ports = [self.portpool.get_port(pid) for pid in port_ids 
                 if self.portpool.has_port_by_id(pid)]
        
        if len(ports) >= 3:
            line = ServiceLine("OptTest", ports, _test=True)
            service_graph = ServiceGraph([line])
            
            # Graph should have methods needed for optimization
            self.assertTrue(hasattr(service_graph, 'tolist_serviceLine'))
            self.assertTrue(hasattr(service_graph, 'get_all_paths'))
            
            # Should be able to get adjacency matrix
            adj_matrix = line.get_adjacency_matrix(self.portpool)
            self.assertIsNotNone(adj_matrix)


class TestProformaDataStructure(unittest.TestCase):
    """Test proforma data structure and content"""
    
    def setUp(self):
        """Load proforma data"""
        self.proforma_path = Path(__file__).parent.parent / 'for_nus' / 'input' / 'proforma_CNC.csv'
        if self.proforma_path.exists():
            self.df = pd.read_csv(self.proforma_path)
        else:
            self.df = None
    
    def test_proforma_has_service_identifiers(self):
        """Test proforma has service line identifiers"""
        if self.df is None:
            self.skipTest("Proforma file not found")
        
        # Should have linename column
        self.assertIn('linename', self.df.columns)
        
        # Services should have meaningful names
        services = self.df['linename'].unique()
        self.assertGreater(len(services), 0)
        
        # Service names should be strings
        for service in services[:5]:  # Check first 5
            self.assertIsInstance(service, str)
    
    def test_proforma_has_port_rotations(self):
        """Test proforma contains port rotation information"""
        if self.df is None:
            self.skipTest("Proforma file not found")
        
        # Should have portid column
        self.assertIn('portid', self.df.columns)
        
        # Port IDs should be non-empty
        port_ids = self.df['portid'].dropna()
        self.assertGreater(len(port_ids), 0)
    
    def test_proforma_has_vessel_information(self):
        """Test proforma contains vessel rank/class information"""
        if self.df is None:
            self.skipTest("Proforma file not found")
        
        # Should have vrank column
        self.assertIn('vrank', self.df.columns)
        
        # Ranks should be numeric
        ranks = self.df['vrank'].dropna()
        self.assertGreater(len(ranks), 0)
        
        # Ranks should be in valid range (1-11)
        for rank in ranks:
            if pd.notna(rank):
                self.assertGreaterEqual(rank, 1)
                self.assertLessEqual(rank, 11)


if __name__ == '__main__':
    unittest.main(verbosity=2)
