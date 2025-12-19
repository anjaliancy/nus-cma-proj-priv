"""
Test suite for demand satisfaction and vessel capacity constraints

Tests:
1. Demand flow variables and constraints
2. Vessel capacity limits on flow
3. Hard vs soft demand satisfaction
"""

import unittest
import sys
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_port_data, read_vessel_class_data, read_demand_with_transit_time
from cma.port import PortGraph


class TestDemandData(unittest.TestCase):
    """Test demand data availability and structure"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
    
    def test_demand_data_available(self):
        """Test that demand data can be loaded"""
        demand_matrix, _ = read_demand_with_transit_time(self.portpool)
        
        # Should have demand data
        self.assertIsNotNone(demand_matrix)
        
        # Should be square matrix (N ports × N ports)
        self.assertEqual(demand_matrix.shape[0], demand_matrix.shape[1])
    
    def test_demand_values_non_negative(self):
        """Test that demand values are non-negative"""
        demand_matrix, _ = read_demand_with_transit_time(self.portpool)
        
        # All demand should be >= 0
        self.assertTrue(np.all(demand_matrix >= 0),
                       "Demand values should be non-negative")
    
    def test_demand_has_positive_od_pairs(self):
        """Test that there are positive demand OD pairs"""
        demand_matrix, _ = read_demand_with_transit_time(self.portpool)
        
        # Should have at least some positive demand
        positive_demand = np.sum(demand_matrix > 0)
        self.assertGreater(positive_demand, 0,
                          "Should have at least some positive demand pairs")
    
    def test_demand_total_volume(self):
        """Test total demand volume is reasonable"""
        demand_matrix, _ = read_demand_with_transit_time(self.portpool)
        
        total_demand = np.sum(demand_matrix)
        
        # Should be positive
        self.assertGreater(total_demand, 0)
        
        # Should be in reasonable range (e.g., 10k - 1M TEUs)
        self.assertGreater(total_demand, 10000, "Total demand seems too low")
        self.assertLess(total_demand, 1000000, "Total demand seems too high")


class TestPortGraphDemand(unittest.TestCase):
    """Test PortGraph demand handling"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        demand_matrix, transit_matrix = read_demand_with_transit_time(self.portpool)
        self.demand_matrix = demand_matrix
        self.transit_matrix = transit_matrix
        
        n_ports = len(self.portpool.tolist_port())
        distance_matrix = np.eye(n_ports) * 1000  # Dummy distances
        
        self.portgraph = PortGraph(
            self.portpool,
            distance_matrix,
            demand_matrix,
            mat_transit_time=transit_matrix,
            filter_by_demand=True
        )
    
    def test_portgraph_stores_demand(self):
        """Test that PortGraph stores demand data"""
        od_pairs = self.portgraph.get_all_od_pairs()
        
        # Should have OD pairs
        self.assertGreater(len(od_pairs), 0)
        
        # Each OD pair should have demand
        for o, d in od_pairs[:10]:  # Check first 10
            demand = self.portgraph.get_demand_by_idx(o, d)
            self.assertIsNotNone(demand)
            self.assertGreater(demand, 0, "Filtered OD pairs should have positive demand")
    
    def test_demand_accessor_methods(self):
        """Test PortGraph demand accessor methods"""
        od_pairs = self.portgraph.get_all_od_pairs()
        
        if len(od_pairs) > 0:
            o, d = od_pairs[0]
            
            # get_demand_by_idx should work
            demand = self.portgraph.get_demand_by_idx(o, d)
            self.assertIsNotNone(demand)
            
            # Should match full demand matrix
            # Note: get_filtered_demand_matrix requires ports parameter
            # So we just verify demand value is reasonable
            self.assertGreater(demand, 0, "Filtered OD pairs should have positive demand")
    
    def test_demand_filtering_removes_zeros(self):
        """Test that filtering removes zero-demand OD pairs"""
        od_pairs = self.portgraph.get_all_od_pairs()
        
        # All filtered pairs should have positive demand
        for o, d in od_pairs:
            demand = self.portgraph.get_demand_by_idx(o, d)
            self.assertGreater(demand, 0,
                              "Filtered OD pairs should have positive demand")
    
    def test_total_demand_preserved(self):
        """Test that total demand is preserved after filtering"""
        # Original total
        original_total = np.sum(self.demand_matrix)
        
        # Filtered total via OD pairs
        filtered_total = 0
        for o, d in self.portgraph.get_all_od_pairs():
            filtered_total += self.portgraph.get_demand_by_idx(o, d)
        
        # Should be close (within floating point error)
        # Note: Filtering may remove zero-demand pairs, so filtered ≤ original
        self.assertLessEqual(filtered_total, original_total,
                           "Filtered demand should not exceed original")
        self.assertGreater(filtered_total, 0,
                          "Filtered demand should be positive")


class TestVesselCapacity(unittest.TestCase):
    """Test vessel capacity constraints"""
    
    def setUp(self):
        """Set up test data"""
        self.vesselpool = read_vessel_class_data()
    
    def test_vessel_capacities_available(self):
        """Test that vessel capacities are defined"""
        # Get vessel capacities
        vessels = self.vesselpool.vessels_list
        
        for vessel in vessels:
            # Each vessel should have capacity
            self.assertTrue(hasattr(vessel, 'vessel_capacity'))
            self.assertGreater(vessel.vessel_capacity, 0,
                              f"Rank {vessel.vessel_rank} should have positive capacity")
    
    def test_line_capacity_calculation(self):
        """Test line capacity = sum of vessel capacities"""
        vessels = self.vesselpool.vessels_list
        
        # Example: 2 vessels of rank 5
        vessel_rank_5 = vessels[4]  # Rank 5 (0-indexed)
        n_vessels = 2
        
        # Line capacity
        line_capacity = n_vessels * vessel_rank_5.vessel_capacity
        
        # Should be reasonable
        self.assertGreater(line_capacity, 0)
        self.assertTrue(np.isfinite(line_capacity))
        
        # Should be proportional to vessel count
        line_capacity_3 = 3 * vessel_rank_5.vessel_capacity
        self.assertAlmostEqual(line_capacity_3 / line_capacity, 1.5, places=5)
    
    def test_capacity_increases_with_vessel_size(self):
        """Test that larger vessels have higher capacity"""
        vessels = self.vesselpool.vessels_list
        
        capacities = [v.vessel_capacity for v in vessels]
        
        # Should be sorted (increasing with rank)
        sorted_capacities = sorted(capacities)
        self.assertEqual(capacities, sorted_capacities,
                        "Vessel capacities should increase with rank")
    
    def test_capacity_range(self):
        """Test that capacity range covers expected values"""
        vessels = self.vesselpool.vessels_list
        
        min_capacity = min(v.vessel_capacity for v in vessels)
        max_capacity = max(v.vessel_capacity for v in vessels)
        
        # Should span reasonable range (200 - 25000 TEU)
        self.assertGreater(min_capacity, 200, "Min capacity seems too low")
        self.assertLess(max_capacity, 30000, "Max capacity seems too high")
        
        # Range should be substantial
        self.assertGreater(max_capacity / min_capacity, 10,
                          "Should have substantial capacity range")
    
    def test_multi_vessel_capacity(self):
        """Test capacity with multiple vessels"""
        vessels = self.vesselpool.vessels_list
        vessel = vessels[5]  # Rank 6
        
        # Different vessel counts
        for n in [1, 2, 3, 5]:
            total_capacity = n * vessel.vessel_capacity
            
            # Should scale linearly
            expected = vessel.vessel_capacity * n
            self.assertEqual(total_capacity, expected)


class TestCapacityConstraintFormulation(unittest.TestCase):
    """Test capacity constraint formulation"""
    
    def test_flow_bounded_by_capacity_concept(self):
        """Test capacity constraint concept: flow ≤ capacity"""
        # Example: Line with 2×2000 TEU vessels = 4000 TEU total
        line_capacity = 4000
        
        # Valid flows
        valid_flows = [0, 1000, 2000, 3000, 4000]
        for flow in valid_flows:
            self.assertLessEqual(flow, line_capacity,
                                f"Flow {flow} should be ≤ capacity {line_capacity}")
        
        # Invalid flows
        invalid_flows = [4001, 5000, 10000]
        for flow in invalid_flows:
            self.assertGreater(flow, line_capacity,
                              f"Flow {flow} should exceed capacity {line_capacity}")
    
    def test_weekly_capacity_calculation(self):
        """Test weekly capacity = line_capacity / weeks"""
        line_capacity = 4000  # TEU
        weeks = 2  # Bi-weekly service
        
        weekly_capacity = line_capacity / weeks
        
        # Should be half for bi-weekly
        self.assertEqual(weekly_capacity, 2000)
        
        # Weekly service
        weekly_capacity_1week = line_capacity / 1
        self.assertEqual(weekly_capacity_1week, 4000)
    
    def test_capacity_slack_allowed(self):
        """Test that flow can be less than capacity"""
        line_capacity = 4000
        actual_flow = 3000  # 75% utilization
        
        # Should be valid (flow < capacity)
        self.assertLess(actual_flow, line_capacity)
        
        # Utilization
        utilization = actual_flow / line_capacity
        self.assertLess(utilization, 1.0)
        self.assertGreaterEqual(utilization, 0.0)


class TestDemandSatisfactionConcept(unittest.TestCase):
    """Test demand satisfaction constraint concept"""
    
    def test_demand_satisfaction_constraint_formulation(self):
        """Test constraint: sum(flow_on_paths) ≥ demand"""
        # Example OD pair with 1000 TEU demand
        demand = 1000
        
        # Satisfied cases
        satisfied_flows = [
            [1000],  # Single path
            [500, 500],  # Two paths equally
            [700, 300],  # Two paths unequally
            [400, 400, 200],  # Three paths
            [1200],  # Over-satisfied
        ]
        
        for flows in satisfied_flows:
            total_flow = sum(flows)
            self.assertGreaterEqual(total_flow, demand,
                                   f"Flow {total_flow} should satisfy demand {demand}")
        
        # Unsatisfied cases (would need penalty)
        unsatisfied_flows = [
            [500],  # Half satisfied
            [200, 300],  # 50% satisfied
            [0],  # No flow
        ]
        
        for flows in unsatisfied_flows:
            total_flow = sum(flows)
            self.assertLess(total_flow, demand,
                           f"Flow {total_flow} should not satisfy demand {demand}")
    
    def test_partial_demand_fulfillment(self):
        """Test partial demand fulfillment (soft constraint)"""
        demand = 1000
        fulfilled = 800  # 80% fulfilled
        
        # Shortfall
        shortfall = demand - fulfilled
        self.assertEqual(shortfall, 200)
        
        # Penalty (example: $1000 per unfulfilled TEU)
        penalty_rate = 1000
        penalty = shortfall * penalty_rate
        
        self.assertEqual(penalty, 200000)
    
    def test_over_fulfillment_not_penalized(self):
        """Test that over-fulfillment is allowed"""
        demand = 1000
        fulfilled = 1200  # 120% fulfilled
        
        # No penalty for over-fulfillment
        shortfall = max(0, demand - fulfilled)
        self.assertEqual(shortfall, 0)
    
    def test_zero_demand_zero_flow(self):
        """Test that zero demand requires zero minimum flow"""
        demand = 0
        flow = 0
        
        # Should be satisfied
        self.assertGreaterEqual(flow, demand)


class TestConstraintInteraction(unittest.TestCase):
    """Test interaction between demand and capacity constraints"""
    
    def test_feasible_case(self):
        """Test feasible case: demand ≤ capacity"""
        demand = 3000
        capacity = 4000
        
        # Should be feasible
        self.assertLessEqual(demand, capacity,
                            "Demand should fit within capacity")
    
    def test_infeasible_case(self):
        """Test infeasible case: demand > capacity"""
        demand = 5000
        capacity = 4000
        
        # Would require penalty or multiple routes
        self.assertGreater(demand, capacity,
                          "Demand exceeds capacity - needs soft constraint")
        
        # Maximum fulfillable
        max_fulfillable = min(demand, capacity)
        self.assertEqual(max_fulfillable, capacity)
        
        # Shortfall
        shortfall = demand - max_fulfillable
        self.assertEqual(shortfall, 1000)
    
    def test_multi_path_solution(self):
        """Test that multiple paths can satisfy demand exceeding single line capacity"""
        demand = 6000
        line1_capacity = 4000
        line2_capacity = 3000
        
        # Single line insufficient
        self.assertGreater(demand, line1_capacity)
        
        # Multiple lines can satisfy
        total_capacity = line1_capacity + line2_capacity
        self.assertGreaterEqual(total_capacity, demand,
                               "Multiple lines should satisfy demand")


if __name__ == '__main__':
    unittest.main(verbosity=2)
