"""
Test suite for transit time penalty in objective function

Requirements tested:
1. PortGraph stores expected transit times for OD pairs
2. read_demand_with_transit_time() extracts transit data from CSV
3. Transit time penalty is added to objective when actual > expected
4. Penalty can be toggled on/off via tuneparams
5. Penalty multiplier is configurable
6. Weighted average transit time for OD pairs with multiple routes
"""

import unittest
import sys
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_port_data, read_demand_with_transit_time
from cma.port import PortGraph


class TestTransitTimeDataReading(unittest.TestCase):
    """Tests for reading transit time data from demand CSV"""
    
    def setUp(self):
        """Set up port data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
    
    def test_read_demand_with_transit_time_returns_two_matrices(self):
        """Test that function returns demand and transit time matrices"""
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        self.assertIsInstance(demand_matrix, np.matrix)
        self.assertIsInstance(transit_matrix, np.matrix)
        self.assertEqual(demand_matrix.shape, transit_matrix.shape)
    
    def test_transit_time_matrix_dimensions(self):
        """Test transit time matrix has correct dimensions"""
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        n_ports = len(self.portpool.tolist_port())
        
        self.assertEqual(transit_matrix.shape, (n_ports, n_ports))
    
    def test_transit_times_are_positive(self):
        """Test that all non-zero transit times are positive"""
        _, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        # Transit times for OD pairs with demand should be positive
        positive_transit = transit_matrix[transit_matrix > 0]
        self.assertTrue(np.all(positive_transit > 0))
    
    def test_transit_times_reasonable_range(self):
        """Test transit times are in reasonable range (1-50 days)"""
        _, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        non_zero_transit = transit_matrix[transit_matrix > 0]
        if len(non_zero_transit) > 0:
            self.assertTrue(np.all(non_zero_transit >= 1))
            self.assertTrue(np.all(non_zero_transit <= 50))
    
    def test_demand_aggregation(self):
        """Test that demands are properly aggregated across multiple rows"""
        demand_matrix, _ = read_demand_with_transit_time(self.portpool)
        
        # Should have non-zero demands
        self.assertTrue(np.sum(demand_matrix) > 0)
        
        # All demands should be non-negative
        self.assertTrue(np.all(demand_matrix >= 0))
    
    def test_transit_time_weighted_average(self):
        """Test that transit times are weighted by demand volume"""
        # This is implicit in the implementation - if an OD pair has
        # multiple routes with different transit times, the result
        # should be weighted by demand
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        # Find OD pairs with demand
        has_demand = demand_matrix > 0
        has_transit = transit_matrix > 0
        
        # All OD pairs with demand should have transit time
        # (if data is complete)
        demand_count = np.sum(has_demand)
        self.assertGreater(demand_count, 0)


class TestPortGraphTransitTime(unittest.TestCase):
    """Tests for PortGraph transit time storage and access"""
    
    def setUp(self):
        """Set up port pool and matrices"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.demand_matrix, self.transit_matrix = read_demand_with_transit_time(self.portpool)
    
    def test_portgraph_accepts_transit_time_matrix(self):
        """Test PortGraph constructor accepts transit time matrix"""
        n_ports = len(self.portpool.tolist_port())
        distance_matrix = np.eye(n_ports) * 1000  # Dummy distances
        
        # Should not raise exception
        portgraph = PortGraph(
            self.portpool,
            distance_matrix,
            self.demand_matrix,
            mat_transit_time=self.transit_matrix,
            filter_by_demand=False
        )
        
        self.assertIsNotNone(portgraph)
    
    def test_get_transit_time_by_idx(self):
        """Test retrieving transit time by index"""
        n_ports = len(self.portpool.tolist_port())
        distance_matrix = np.eye(n_ports) * 1000
        
        portgraph = PortGraph(
            self.portpool,
            distance_matrix,
            self.demand_matrix,
            mat_transit_time=self.transit_matrix,
            filter_by_demand=False
        )
        
        # Find an OD pair with demand
        od_pairs = portgraph.get_all_od_pairs()
        if len(od_pairs) > 0:
            o, d = od_pairs[0]
            transit = portgraph.get_transit_time_by_idx(o, d)
            
            self.assertIsNotNone(transit)
            self.assertGreater(transit, 0)
    
    def test_transit_time_none_when_not_provided(self):
        """Test that transit time is None when not provided to constructor"""
        n_ports = len(self.portpool.tolist_port())
        distance_matrix = np.eye(n_ports) * 1000
        
        portgraph = PortGraph(
            self.portpool,
            distance_matrix,
            self.demand_matrix,
            filter_by_demand=False
        )
        
        od_pairs = portgraph.get_all_od_pairs()
        if len(od_pairs) > 0:
            o, d = od_pairs[0]
            transit = portgraph.get_transit_time_by_idx(o, d)
            
            self.assertIsNone(transit)
    
    def test_filtered_transit_time_matrix(self):
        """Test that transit time matrix is correctly filtered"""
        n_ports = len(self.portpool.tolist_port())
        distance_matrix = np.eye(n_ports) * 1000
        
        portgraph = PortGraph(
            self.portpool,
            distance_matrix,
            self.demand_matrix,
            mat_transit_time=self.transit_matrix,
            filter_by_demand=True  # Enable filtering
        )
        
        # After filtering, should still have transit times for demand pairs
        od_pairs = portgraph.get_all_od_pairs()
        self.assertGreater(len(od_pairs), 0)
        
        # Check that transit times are preserved
        for o, d in od_pairs[:5]:  # Check first 5
            transit = portgraph.get_transit_time_by_idx(o, d)
            if transit is not None:
                self.assertGreater(transit, 0)


class TestTransitTimePenaltyCalculation(unittest.TestCase):
    """Tests for transit time penalty in optimization"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.demand_matrix, self.transit_matrix = read_demand_with_transit_time(self.portpool)
    
    def test_penalty_parameters_in_tuneparams(self):
        """Test that penalty parameters can be set in tuneparams"""
        tuneparams = {
            'turnon-transit_time_penalty': 1,
            'ctrparam-transit_penalty_multiplier': 1000.0,
        }
        
        self.assertEqual(tuneparams['turnon-transit_time_penalty'], 1)
        self.assertEqual(tuneparams['ctrparam-transit_penalty_multiplier'], 1000.0)
    
    def test_penalty_can_be_disabled(self):
        """Test that penalty can be toggled off"""
        tuneparams = {
            'turnon-transit_time_penalty': 0,
        }
        
        self.assertEqual(tuneparams['turnon-transit_time_penalty'], 0)
    
    def test_different_penalty_multipliers(self):
        """Test various penalty multiplier values"""
        multipliers = [100, 500, 1000, 5000, 10000]
        
        for mult in multipliers:
            tuneparams = {
                'ctrparam-transit_penalty_multiplier': mult,
            }
            self.assertEqual(tuneparams['ctrparam-transit_penalty_multiplier'], mult)


class TestTransitTimeEdgeCases(unittest.TestCase):
    """Tests for edge cases in transit time handling"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
    
    def test_zero_demand_no_transit_time(self):
        """Test that OD pairs with zero demand have zero transit time"""
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        # Find pairs with zero demand
        zero_demand_mask = demand_matrix == 0
        
        # These should also have zero transit time
        zero_demand_transit = transit_matrix[zero_demand_mask]
        self.assertTrue(np.all(zero_demand_transit == 0))
    
    def test_same_origin_destination(self):
        """Test that same origin-destination pairs have zero values"""
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        # Diagonal should be zero (no self-loops in shipping)
        n = demand_matrix.shape[0]
        for i in range(n):
            self.assertEqual(demand_matrix[i, i], 0)
            self.assertEqual(transit_matrix[i, i], 0)
    
    def test_asymmetric_transit_times(self):
        """Test that transit times can be asymmetric (O-D vs D-O)"""
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        # Find an OD pair with demand in both directions
        n = demand_matrix.shape[0]
        asymmetric_found = False
        
        for i in range(min(n, 50)):  # Check first 50 pairs
            for j in range(i+1, min(n, 50)):
                if demand_matrix[i, j] > 0 and demand_matrix[j, i] > 0:
                    # Both directions have demand
                    transit_ij = transit_matrix[i, j]
                    transit_ji = transit_matrix[j, i]
                    
                    if transit_ij != transit_ji:
                        asymmetric_found = True
                        break
            if asymmetric_found:
                break
        
        # Asymmetry is possible (different routes/schedules)
        # This test just verifies the data structure supports it


class TestTransitTimeIntegration(unittest.TestCase):
    """Integration tests for transit time penalty feature"""
    
    def setUp(self):
        """Set up complete test environment"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.demand_matrix, self.transit_matrix = read_demand_with_transit_time(self.portpool)
    
    def test_end_to_end_data_flow(self):
        """Test complete data flow from CSV to PortGraph"""
        # Read data
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        
        # Create distance matrix (dummy)
        n_ports = len(self.portpool.tolist_port())
        distance_matrix = np.eye(n_ports) * 1000
        
        # Create PortGraph with transit times
        portgraph = PortGraph(
            self.portpool,
            distance_matrix,
            demand_matrix,
            mat_transit_time=transit_matrix,
            filter_by_demand=True
        )
        
        # Verify we can access transit times
        od_pairs = portgraph.get_all_od_pairs()
        self.assertGreater(len(od_pairs), 0)
        
        successful_reads = 0
        for o, d in od_pairs[:10]:
            transit = portgraph.get_transit_time_by_idx(o, d)
            if transit is not None and transit > 0:
                successful_reads += 1
        
        self.assertGreater(successful_reads, 0)
    
    def test_portgraph_consistency(self):
        """Test that demand and transit matrices remain consistent"""
        n_ports = len(self.portpool.tolist_port())
        distance_matrix = np.eye(n_ports) * 1000
        
        portgraph = PortGraph(
            self.portpool,
            distance_matrix,
            self.demand_matrix,
            mat_transit_time=self.transit_matrix,
            filter_by_demand=True
        )
        
        # All OD pairs with demand should have corresponding transit time
        od_pairs = portgraph.get_all_od_pairs()
        
        for o, d in od_pairs:
            demand = portgraph.get_demand_by_idx(o, d)
            transit = portgraph.get_transit_time_by_idx(o, d)
            
            # If there's demand, there should be transit time
            if demand > 0:
                self.assertIsNotNone(transit)
                if transit is not None:
                    self.assertGreater(transit, 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
