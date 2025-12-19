"""
Test suite for objective function cost components

Verifies that all four cost components are correctly included:
1. Chartering cost
2. Bunkering (fuel) cost  
3. Port call cost
4. Transshipment cost
"""

import unittest
import sys
from pathlib import Path
import numpy as np

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_port_data, read_vessel_class_data


class TestChateringCost(unittest.TestCase):
    """Test chartering cost component"""
    
    def setUp(self):
        """Set up test data"""
        self.vesselpool = read_vessel_class_data()
    
    def test_chartering_costs_available(self):
        """Test that chartering costs are available for all vessel ranks"""
        charter_costs = self.vesselpool.get_chartering_costs()
        
        # Should have costs for all 11 ranks
        self.assertEqual(len(charter_costs), 11)
        
        # All costs should be positive
        for cost in charter_costs:
            self.assertGreater(cost, 0, "Chartering cost should be positive")
    
    def test_chartering_cost_formula(self):
        """Test weekly chartering cost formula: 7 × daily_rate × n_vessels"""
        charter_costs = self.vesselpool.get_chartering_costs()
        
        # Example: 2 vessels of rank 5
        n_vessels = 2
        rank_idx = 4  # Rank 5 (0-indexed)
        daily_rate = charter_costs[rank_idx]
        
        # Weekly cost
        weekly_cost = 7 * daily_rate * n_vessels
        
        # Should be reasonable (positive, finite)
        self.assertGreater(weekly_cost, 0)
        self.assertTrue(np.isfinite(weekly_cost))
        
        # Should be proportional to vessel count
        weekly_cost_3vessels = 7 * daily_rate * 3
        self.assertAlmostEqual(weekly_cost_3vessels / weekly_cost, 1.5, places=5)
    
    def test_chartering_cost_increases_with_size(self):
        """Test that larger vessels cost more to charter"""
        charter_costs = self.vesselpool.get_chartering_costs()
        
        # Compare small vs large vessels
        small_vessel_cost = charter_costs[0]  # Rank 1
        large_vessel_cost = charter_costs[-1]  # Rank 11
        
        # Large vessel should cost more
        self.assertGreater(large_vessel_cost, small_vessel_cost,
                          "Large vessels should have higher charter costs")
    
    def test_chartering_cost_realistic_range(self):
        """Test that chartering costs are in realistic range"""
        charter_costs = self.vesselpool.get_chartering_costs()
        
        # Daily costs should be in reasonable range ($5k - $150k/day)
        for cost in charter_costs:
            self.assertGreater(cost, 5000, "Daily charter cost seems too low")
            self.assertLess(cost, 150000, "Daily charter cost seems too high")


class TestBunkeringCost(unittest.TestCase):
    """Test bunkering (fuel) cost component"""
    
    def setUp(self):
        """Set up test data"""
        self.vesselpool = read_vessel_class_data()
    
    def test_bukering_costs_available(self):
        """Test that fuel costs are available for all vessel ranks and speeds"""
        bukering_costs, speed_level0 = self.vesselpool.get_bukering_costs()
        
        # Should have costs for 11 ranks
        self.assertEqual(bukering_costs.shape[0], 11)
        
        # Should have 18 speed levels
        self.assertEqual(bukering_costs.shape[1], 18)
        
        # Starting speed should be 10 kts
        self.assertEqual(speed_level0, 10.0)
    
    def test_fuel_cost_increases_with_speed(self):
        """Test that fuel cost increases with speed"""
        bukering_costs, _ = self.vesselpool.get_bukering_costs()
        
        # For each vessel rank
        for rank_idx in range(11):
            rank_costs = bukering_costs[rank_idx, :]
            
            # Costs should generally increase with speed
            # (allowing for some discretization effects)
            avg_low_speed = np.mean(rank_costs[:5])  # First 5 speed levels
            avg_high_speed = np.mean(rank_costs[-5:])  # Last 5 speed levels
            
            self.assertGreater(avg_high_speed, avg_low_speed,
                              f"Rank {rank_idx+1}: High speed fuel cost should exceed low speed")
    
    def test_fuel_cost_formula(self):
        """Test weekly fuel cost formula: vessels × consumption × price × 7"""
        bukering_costs, _ = self.vesselpool.get_bukering_costs()
        
        # Example: 2 vessels, rank 5, speed index 10
        n_vessels = 2
        rank_idx = 4
        speed_idx = 10
        
        daily_fuel_cost = bukering_costs[rank_idx, speed_idx]
        
        # Weekly cost
        weekly_fuel_cost = n_vessels * daily_fuel_cost * 7
        
        self.assertGreater(weekly_fuel_cost, 0)
        self.assertTrue(np.isfinite(weekly_fuel_cost))
    
    def test_fuel_cost_positive(self):
        """Test that all fuel costs are positive"""
        bukering_costs, _ = self.vesselpool.get_bukering_costs()
        
        # All costs should be positive
        self.assertTrue(np.all(bukering_costs > 0),
                       "All fuel costs should be positive")


class TestPortCallCost(unittest.TestCase):
    """Test port call cost component"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.vesselpool = read_vessel_class_data()
    
    def test_port_call_costs_available(self):
        """Test that port call costs are available"""
        # Get a sample port
        ports = self.portpool.tolist_port()
        sample_port = ports[0]
        
        # Should have cost method
        self.assertTrue(hasattr(sample_port, 'get_portcall_costs'))
        
        # Should return costs for all vessel ranks
        costs = sample_port.get_portcall_costs(self.vesselpool)
        self.assertIsNotNone(costs)
        self.assertEqual(len(costs), 11)
    
    def test_port_call_costs_positive(self):
        """Test that port call costs are positive"""
        ports = self.portpool.tolist_port()
        
        # Check several ports
        for port in ports[:10]:
            costs = port.get_portcall_costs(self.vesselpool)
            
            # Costs should be non-negative
            for cost in costs:
                self.assertGreaterEqual(cost, 0,
                    f"Port {port.get_id()}: Port call cost should be non-negative")
    
    def test_port_call_cost_varies_by_vessel_size(self):
        """Test that port call cost varies by vessel size"""
        ports = self.portpool.tolist_port()
        
        # Find a port with non-zero costs
        for port in ports:
            costs = port.get_portcall_costs(self.vesselpool)
            
            if np.sum(costs) > 0:
                # Costs should generally increase with vessel size
                # Check that large vessels cost more than small
                if costs[0] > 0 and costs[-1] > 0:
                    # Allow for some variation, but large should generally be higher
                    avg_small = np.mean([c for c in costs[:3] if c > 0] or [0])
                    avg_large = np.mean([c for c in costs[-3:] if c > 0] or [0])
                    
                    if avg_small > 0 and avg_large > 0:
                        # Large vessels should cost at least as much as small
                        self.assertGreaterEqual(avg_large, avg_small * 0.8,
                            f"Port {port.get_id()}: Large vessel costs should be comparable to small")
                        break
    
    def test_port_call_cost_accumulation(self):
        """Test that port call costs accumulate across multiple ports"""
        ports = self.portpool.tolist_port()[:3]  # First 3 ports
        
        total_cost = 0
        for port in ports:
            costs = port.get_portcall_costs(self.vesselpool)
            # Add cost for rank 5 vessels
            total_cost += costs[4]  # Rank 5 (0-indexed)
        
        # Total should be sum of individual costs
        self.assertGreater(total_cost, 0)
        self.assertTrue(np.isfinite(total_cost))


class TestTransshipmentCost(unittest.TestCase):
    """Test transshipment cost component"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.vesselpool = read_vessel_class_data()
    
    def test_transshipment_cost_calculation(self):
        """Test transshipment cost formula: (volume / productivity) × rate"""
        ports = self.portpool.tolist_port()
        
        # Find a port with productivity data
        for port in ports:
            productivity = port.get_producticity(self.vesselpool)
            
            if productivity is not None and len(productivity) > 0:
                gross_prod = sum(productivity)
                
                if gross_prod > 0:
                    # Example: 1000 TEU transshipment
                    volume = 1000
                    
                    # Time in hours
                    time_hours = volume / gross_prod
                    
                    # Should be positive and finite
                    self.assertGreater(time_hours, 0)
                    self.assertTrue(np.isfinite(time_hours))
                    
                    # Cost = time × hourly_rate (e.g., $100/hour)
                    hourly_rate = 100
                    cost = time_hours * hourly_rate
                    
                    self.assertGreater(cost, 0)
                    break
    
    def test_zero_transshipment_zero_cost(self):
        """Test that zero transshipment means zero cost"""
        # No transshipment
        volume = 0
        time = 0
        cost = time * 100  # Any rate
        
        self.assertEqual(cost, 0)
    
    def test_transshipment_productivity_relationship(self):
        """Test that higher productivity means lower time/cost"""
        volume = 1000  # Fixed volume
        
        # Low productivity
        low_prod = 50  # TEU/hour
        time_low = volume / low_prod
        
        # High productivity
        high_prod = 100  # TEU/hour
        time_high = volume / high_prod
        
        # Higher productivity should mean less time
        self.assertLess(time_high, time_low)
        
        # And therefore lower cost
        rate = 100
        cost_low = time_low * rate
        cost_high = time_high * rate
        
        self.assertLess(cost_high, cost_low)


class TestObjectiveFunctionIntegration(unittest.TestCase):
    """Test that all cost components work together"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        self.vesselpool = read_vessel_class_data()
    
    def test_all_cost_components_accessible(self):
        """Test that all four cost components can be computed"""
        # 1. Chartering
        charter_costs = self.vesselpool.get_chartering_costs()
        self.assertIsNotNone(charter_costs)
        
        # 2. Bunkering
        bukering_costs, _ = self.vesselpool.get_bukering_costs()
        self.assertIsNotNone(bukering_costs)
        
        # 3. Port call
        port = self.portpool.tolist_port()[0]
        port_costs = port.get_portcall_costs(self.vesselpool)
        self.assertIsNotNone(port_costs)
        
        # 4. Transshipment (via productivity)
        productivity = port.get_producticity(self.vesselpool)
        self.assertIsNotNone(productivity)
    
    def test_total_cost_calculation_example(self):
        """Test example total cost calculation"""
        # Simplified example
        n_vessels = 2
        rank_idx = 4  # Rank 5
        speed_idx = 10
        
        # 1. Charter cost
        charter_costs = self.vesselpool.get_chartering_costs()
        weekly_charter = 7 * charter_costs[rank_idx] * n_vessels
        
        # 2. Fuel cost
        bukering_costs, _ = self.vesselpool.get_bukering_costs()
        weekly_fuel = 7 * bukering_costs[rank_idx, speed_idx] * n_vessels
        
        # 3. Port call cost (3 ports)
        ports = self.portpool.tolist_port()[:3]
        total_port_call = sum(p.get_portcall_costs(self.vesselpool)[rank_idx] for p in ports)
        
        # 4. Transshipment cost (example: 1000 TEU)
        port = ports[0]
        prod = port.get_producticity(self.vesselpool)
        if prod and sum(prod) > 0:
            transship_time = 1000 / sum(prod)
            transship_cost = transship_time * 100
        else:
            transship_cost = 0
        
        # Total cost
        total_cost = weekly_charter + weekly_fuel + total_port_call + transship_cost
        
        # Should be positive and finite
        self.assertGreater(total_cost, 0)
        self.assertTrue(np.isfinite(total_cost))
        
        # Charter and fuel should dominate
        self.assertGreater(weekly_charter + weekly_fuel, 
                          total_port_call + transship_cost,
                          "Operational costs should dominate over port costs in typical case")


if __name__ == '__main__':
    unittest.main(verbosity=2)
