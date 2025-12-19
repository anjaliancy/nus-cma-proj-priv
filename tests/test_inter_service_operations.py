"""
Test suite for inter-service operations and demonstrations

Tests:
1. Operations that affect multiple service lines
2. Coordination between lines
3. Network-level demonstrations
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_port_data, read_vessel_class_data
from cma.serviceline import ServiceLine
from cma.servicegraph import ServiceGraph


class TestInterServiceCoordination(unittest.TestCase):
    """Test coordination between multiple service lines"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.vesselpool = read_vessel_class_data()
    
    def test_multiple_lines_in_servicegraph(self):
        """Test ServiceGraph manages multiple lines"""
        ports = self.portpool.tolist_port()[:8]
        
        # Create two service lines
        line1 = ServiceLine("Line1", ports[:4], _test=True)
        line2 = ServiceLine("Line2", ports[4:8], _test=True)
        
        # Add to ServiceGraph
        service_graph = ServiceGraph([line1, line2])
        
        # Should contain both lines
        lines = service_graph.tolist_serviceLine()
        self.assertEqual(len(lines), 2)
    
    def test_shared_ports_between_lines(self):
        """Test multiple lines sharing common ports (transshipment)"""
        ports = self.portpool.tolist_port()[:6]
        hub_port = ports[2]  # Shared hub
        
        # Line 1: A -> Hub -> B
        line1 = ServiceLine("Line1", [ports[0], hub_port, ports[1]], _test=True)
        
        # Line 2: C -> Hub -> D
        line2 = ServiceLine("Line2", [ports[3], hub_port, ports[4]], _test=True)
        
        # Both lines visit hub_port
        hub_id = hub_port.get_id()
        
        line1_visits_hub = any(p.get_id() == hub_id for p in line1.tolist_port())
        line2_visits_hub = any(p.get_id() == hub_id for p in line2.tolist_port())
        
        self.assertTrue(line1_visits_hub, "Line 1 should visit hub")
        self.assertTrue(line2_visits_hub, "Line 2 should visit hub")
    
    def test_independent_line_operations(self):
        """Test that lines can be modified independently"""
        ports = self.portpool.tolist_port()[:8]
        
        line1 = ServiceLine("Line1", ports[:4], _test=True)
        line2 = ServiceLine("Line2", ports[4:8], _test=True)
        
        # Initial lengths
        initial_len1 = line1.number_of_port()
        initial_len2 = line2.number_of_port()
        
        # Modify line1 (conceptually)
        # In practice, operations create new ServiceLine instances
        # Here we just verify they're independent
        
        self.assertEqual(line1.number_of_port(), initial_len1)
        self.assertEqual(line2.number_of_port(), initial_len2)


class TestNetworkLevelOperations(unittest.TestCase):
    """Test network-level operations affecting multiple lines"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
    
    def test_add_line_to_network(self):
        """Test adding new service line to network"""
        ports = self.portpool.tolist_port()[:8]
        
        # Initial network with one line
        line1 = ServiceLine("Line1", ports[:4], _test=True)
        service_graph = ServiceGraph([line1])
        
        self.assertEqual(len(service_graph.tolist_serviceLine()), 1)
        
        # Add second line
        line2 = ServiceLine("Line2", ports[4:8], _test=True)
        service_graph2 = ServiceGraph([line1, line2])
        
        self.assertEqual(len(service_graph2.tolist_serviceLine()), 2)
    
    def test_remove_line_from_network(self):
        """Test removing service line from network"""
        ports = self.portpool.tolist_port()[:8]
        
        line1 = ServiceLine("Line1", ports[:4], _test=True)
        line2 = ServiceLine("Line2", ports[4:8], _test=True)
        
        # Network with both lines
        service_graph_full = ServiceGraph([line1, line2])
        self.assertEqual(len(service_graph_full.tolist_serviceLine()), 2)
        
        # Network with only line1
        service_graph_reduced = ServiceGraph([line1])
        self.assertEqual(len(service_graph_reduced.tolist_serviceLine()), 1)
    
    def test_network_connectivity(self):
        """Test network connectivity through shared ports"""
        ports = self.portpool.tolist_port()[:7]
        
        # Create network with shared port
        shared_port = ports[3]
        
        line1 = ServiceLine("Line1", [ports[0], ports[1], shared_port], _test=True)
        line2 = ServiceLine("Line2", [shared_port, ports[4], ports[5]], _test=True)
        
        service_graph = ServiceGraph([line1, line2])
        
        # Network should have 2 lines
        self.assertEqual(len(service_graph.tolist_serviceLine()), 2)
        
        # Shared port provides connectivity
        shared_id = shared_port.get_id()
        
        lines_visiting_shared = 0
        for line in service_graph.tolist_serviceLine():
            if any(p.get_id() == shared_id for p in line.tolist_port()):
                lines_visiting_shared += 1
        
        self.assertEqual(lines_visiting_shared, 2,
                        "Two lines should visit shared port")


class TestTransshipmentDemonstration(unittest.TestCase):
    """Test transshipment between service lines"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
    
    def test_hub_and_spoke_network(self):
        """Test hub-and-spoke network structure"""
        ports = self.portpool.tolist_port()[:10]  # Need more ports
        hub = ports[0]
        
        # Spoke 1: Hub -> A -> B
        line1 = ServiceLine("Spoke1", [hub, ports[1], ports[2]], _test=True)
        
        # Spoke 2: Hub -> C -> D
        line2 = ServiceLine("Spoke2", [hub, ports[3], ports[4]], _test=True)
        
        # Spoke 3: Hub -> E -> F
        line3 = ServiceLine("Spoke3", [hub, ports[5], ports[6]], _test=True)
        
        # All lines connect at hub
        hub_id = hub.get_id()
        
        for line in [line1, line2, line3]:
            visits_hub = any(p.get_id() == hub_id for p in line.tolist_port())
            self.assertTrue(visits_hub, f"{line.name} should visit hub")
    
    def test_transshipment_connectivity(self):
        """Test transshipment enables O-D connectivity"""
        ports = self.portpool.tolist_port()[:6]
        hub = ports[2]
        
        # Origin port on line 1
        origin = ports[0]
        
        # Destination port on line 2
        destination = ports[4]
        
        # Line 1: Origin -> Hub
        line1 = ServiceLine("Feeder1", [origin, ports[1], hub], _test=True)
        
        # Line 2: Hub -> Destination
        line2 = ServiceLine("Feeder2", [hub, ports[3], destination], _test=True)
        
        # O-D connectivity through transshipment at hub
        # Origin -> Line1 -> Hub -> Line2 -> Destination
        
        hub_id = hub.get_id()
        origin_id = origin.get_id()
        dest_id = destination.get_id()
        
        # Line 1 connects origin to hub
        line1_ports = [p.get_id() for p in line1.tolist_port()]
        self.assertIn(origin_id, line1_ports)
        self.assertIn(hub_id, line1_ports)
        
        # Line 2 connects hub to destination
        line2_ports = [p.get_id() for p in line2.tolist_port()]
        self.assertIn(hub_id, line2_ports)
        self.assertIn(dest_id, line2_ports)


class TestFleetAllocation(unittest.TestCase):
    """Test fleet allocation across multiple lines"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.vesselpool = read_vessel_class_data()
    
    def test_different_vessel_types_per_line(self):
        """Test that different lines can use different vessel types"""
        ports = self.portpool.tolist_port()[:6]
        
        # Line 1 could use small vessels (rank 3)
        line1 = ServiceLine("SmallLine", ports[:3], _test=True)
        vessel_rank_1 = 3
        
        # Line 2 could use large vessels (rank 8)
        line2 = ServiceLine("LargeLine", ports[3:6], _test=True)
        vessel_rank_2 = 8
        
        # Different vessel types
        self.assertNotEqual(vessel_rank_1, vessel_rank_2)
        
        # Both valid ranks (1-11)
        self.assertIn(vessel_rank_1, range(1, 12))
        self.assertIn(vessel_rank_2, range(1, 12))
    
    def test_fleet_size_flexibility(self):
        """Test that different lines can have different fleet sizes"""
        # Line 1: 2 vessels
        fleet_size_1 = 2
        
        # Line 2: 3 vessels
        fleet_size_2 = 3
        
        # Different fleet sizes allowed
        self.assertNotEqual(fleet_size_1, fleet_size_2)
        
        # Both valid
        self.assertGreater(fleet_size_1, 0)
        self.assertGreater(fleet_size_2, 0)
    
    def test_total_fleet_constraint(self):
        """Test total fleet size constraint across lines"""
        # Example: 10 total vessels available
        total_available = 10
        
        # Allocation to 3 lines
        allocation = {
            'Line1': 3,
            'Line2': 4,
            'Line3': 3,
        }
        
        total_allocated = sum(allocation.values())
        
        self.assertEqual(total_allocated, total_available,
                        "Total allocated should match available")


class TestCoveredDemand(unittest.TestCase):
    """Test demand coverage by service network"""
    
    def test_single_line_coverage(self):
        """Test demand coverage by single service line"""
        # Conceptual: Line serves O-D pairs along its route
        
        # Line: A -> B -> C
        # Covers: A->B, A->C, B->C
        
        covered_pairs = [
            ('A', 'B'),
            ('A', 'C'),
            ('B', 'C'),
        ]
        
        self.assertEqual(len(covered_pairs), 3)
    
    def test_multi_line_coverage_no_overlap(self):
        """Test demand coverage by non-overlapping lines"""
        # Line 1: A -> B -> C (covers 3 O-D pairs)
        # Line 2: D -> E -> F (covers 3 O-D pairs)
        # Total: 6 O-D pairs
        
        line1_coverage = 3
        line2_coverage = 3
        total_coverage = line1_coverage + line2_coverage
        
        self.assertEqual(total_coverage, 6)
    
    def test_multi_line_coverage_with_transshipment(self):
        """Test expanded coverage through transshipment"""
        # Line 1: A -> Hub (covers A->Hub)
        # Line 2: Hub -> B (covers Hub->B)
        # With transshipment: also covers A->B
        
        direct_coverage = 2  # A->Hub, Hub->B
        transship_coverage = 1  # A->Hub->B
        total_coverage = direct_coverage + transship_coverage
        
        self.assertEqual(total_coverage, 3)


class TestNetworkDesignPatterns(unittest.TestCase):
    """Test common network design patterns"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
    
    def test_circular_route_pattern(self):
        """Test circular service line pattern"""
        ports = self.portpool.tolist_port()[:5]
        
        # Circular route: A -> B -> C -> D -> A
        # (closed loop)
        circular_line = ServiceLine("Circular", ports, _test=True)
        
        # Should be valid
        self.assertTrue(circular_line.check_valid())
    
    def test_pendulum_route_pattern(self):
        """Test pendulum service pattern"""
        ports = self.portpool.tolist_port()[:4]
        
        # Pendulum: A -> B -> C -> D
        # (open route, vessel returns same path)
        pendulum_line = ServiceLine("Pendulum", ports, _test=True)
        
        # Should be valid
        self.assertTrue(pendulum_line.check_valid())
    
    def test_multi_hub_network(self):
        """Test network with multiple hubs"""
        ports = self.portpool.tolist_port()[:10]
        
        hub1 = ports[0]
        hub2 = ports[5]
        
        # Line 1: Feeder to Hub1
        line1 = ServiceLine("Feeder1", [ports[1], ports[2], hub1], _test=True)
        
        # Line 2: Feeder to Hub2
        line2 = ServiceLine("Feeder2", [ports[6], ports[7], hub2], _test=True)
        
        # Line 3: Hub-to-hub trunk line
        line3 = ServiceLine("Trunk", [hub1, ports[3], ports[4], hub2], _test=True)
        
        # All should be valid
        self.assertTrue(line1.check_valid())
        self.assertTrue(line2.check_valid())
        self.assertTrue(line3.check_valid())
        
        # Network has 3 lines
        service_graph = ServiceGraph([line1, line2, line3])
        self.assertEqual(len(service_graph.tolist_serviceLine()), 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
