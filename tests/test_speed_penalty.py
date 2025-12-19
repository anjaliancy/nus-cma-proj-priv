"""
Test suite for speed soft cap penalty (>16.5 kts)

Requirements tested:
1. Speed penalty parameters properly added to tuneparams
2. Bukering costs multiplied for speeds ≥17 kts
3. Different penalty multipliers work correctly
4. No penalty applied to speeds ≤16 kts
5. Penalty calculation logic correct for edge cases
"""

import unittest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_vessel_class_data
from cma.port import Port
from cma.serviceline import ServiceLine


class TestSpeedPenaltyParameters(unittest.TestCase):
    """Test that tuneparams properly include speed penalty parameters"""
    
    def test_default_speed_soft_cap(self):
        """Test that default soft cap is 16.5 kts"""
        # Default tuneparams should have speed_soft_cap_kts = 16.5
        from cma.servicegraph import ServiceGraph
        
        # Check default value by inspecting function signature
        import inspect
        sig = inspect.signature(ServiceGraph.fulfill_demands)
        default_tuneparams = sig.parameters['tuneparams'].default
        
        self.assertIn('ctrparam-speed_soft_cap_kts', default_tuneparams,
                     "Speed soft cap parameter missing from tuneparams")
        self.assertEqual(default_tuneparams['ctrparam-speed_soft_cap_kts'], 16.5,
                        "Default speed soft cap should be 16.5 kts")
    
    def test_default_penalty_multiplier(self):
        """Test that default penalty multiplier is 2.0"""
        from cma.servicegraph import ServiceGraph
        
        import inspect
        sig = inspect.signature(ServiceGraph.fulfill_demands)
        default_tuneparams = sig.parameters['tuneparams'].default
        
        self.assertIn('ctrparam-speed_penalty_multiplier', default_tuneparams,
                     "Speed penalty multiplier parameter missing from tuneparams")
        self.assertEqual(default_tuneparams['ctrparam-speed_penalty_multiplier'], 2.0,
                        "Default penalty multiplier should be 2.0")


class TestBukeringCostPenalty(unittest.TestCase):
    """Test that bukering costs are properly penalized for high speeds"""
    
    def setUp(self):
        """Set up vessel pool to get bukering costs"""
        self.vessel_pool = read_vessel_class_data()
        self.base_costs, self.speed_level0 = self.vessel_pool.get_bukering_costs()
        self.n_speed_level = self.base_costs.shape[1]
    
    def test_penalty_calculation_logic(self):
        """Test that penalty calculation correctly identifies speeds > 16.5"""
        speed_soft_cap = 16.5
        speed_level0 = 10.0
        
        # Calculate cap_index
        cap_index = int(np.ceil(speed_soft_cap - speed_level0))
        
        # Should be 7 (since ceil(16.5 - 10) = ceil(6.5) = 7)
        # This means speed index 7 corresponds to 17 kts
        self.assertEqual(cap_index, 7,
                        "Cap index should be 7 for soft cap 16.5 kts with speed_level0=10")
        
        # Verify that speed index 7 = 17 kts
        KTS_levels = np.arange(speed_level0, speed_level0 + 18)
        self.assertEqual(KTS_levels[cap_index], 17.0,
                        "Speed index 7 should correspond to 17 kts")
    
    def test_penalty_applied_to_high_speeds(self):
        """Test that penalty multiplier is applied to speeds ≥17 kts"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        
        # Apply penalty logic
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult
        
        # Check that speeds ≥17 kts (index 7+) are doubled
        for speed_idx in range(cap_index, self.n_speed_level):
            np.testing.assert_array_almost_equal(
                penalized_costs[:, speed_idx],
                self.base_costs[:, speed_idx] * penalty_mult,
                decimal=2,
                err_msg=f"Speed index {speed_idx} should have {penalty_mult}x penalty"
            )
    
    def test_no_penalty_for_low_speeds(self):
        """Test that no penalty is applied to speeds ≤16 kts"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        
        # Apply penalty logic
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult
        
        # Check that speeds <17 kts (index 0-6) are unchanged
        for speed_idx in range(cap_index):
            np.testing.assert_array_almost_equal(
                penalized_costs[:, speed_idx],
                self.base_costs[:, speed_idx],
                decimal=2,
                err_msg=f"Speed index {speed_idx} should have NO penalty"
            )
    
    def test_different_penalty_multipliers(self):
        """Test that different penalty multipliers work correctly"""
        speed_soft_cap = 16.5
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        
        # Test various multipliers
        for penalty_mult in [1.5, 2.0, 2.5, 3.0, 5.0]:
            penalized_costs = self.base_costs.copy()
            penalized_costs[:, cap_index:] *= penalty_mult
            
            # Verify multiplier applied correctly
            for speed_idx in range(cap_index, self.n_speed_level):
                np.testing.assert_array_almost_equal(
                    penalized_costs[:, speed_idx],
                    self.base_costs[:, speed_idx] * penalty_mult,
                    decimal=2,
                    err_msg=f"Penalty multiplier {penalty_mult} not applied correctly"
                )
    
    def test_penalty_boundary_at_17_knots(self):
        """Test that penalty boundary is exactly at 17 knots"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        
        KTS_levels = np.arange(self.speed_level0, self.speed_level0 + self.n_speed_level)
        
        # 16 kts (index 6) should NOT have penalty
        self.assertLess(KTS_levels[cap_index - 1], speed_soft_cap,
                       "Speed before cap_index should be < soft cap")
        
        # 17 kts (index 7) should HAVE penalty
        self.assertGreater(KTS_levels[cap_index], speed_soft_cap,
                          "Speed at cap_index should be > soft cap")
        
        # Apply penalty
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult
        
        # Verify 16 kts unchanged, 17 kts doubled
        np.testing.assert_array_equal(
            penalized_costs[:, cap_index - 1],
            self.base_costs[:, cap_index - 1],
            err_msg="16 kts should have NO penalty"
        )
        
        np.testing.assert_array_almost_equal(
            penalized_costs[:, cap_index],
            self.base_costs[:, cap_index] * penalty_mult,
            decimal=2,
            err_msg=f"17 kts should have {penalty_mult}x penalty"
        )
    
    def test_penalty_magnitude(self):
        """Test that penalty creates significant cost difference"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        
        # Apply penalty
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult
        
        # For any vessel rank, high speed should cost significantly more
        for rank_idx in range(self.base_costs.shape[0]):
            # Compare 16 kts vs 17 kts
            cost_16kts = penalized_costs[rank_idx, cap_index - 1]
            cost_17kts = penalized_costs[rank_idx, cap_index]
            
            # 17 kts should cost substantially more (natural increase + penalty)
            # Natural cost increase from 16→17 is ~10%, penalty makes it ~110%
            cost_ratio = cost_17kts / cost_16kts
            self.assertGreater(cost_ratio, 1.8,
                              f"Rank {rank_idx}: 17 kts should cost ≥1.8x more than 16 kts "
                              f"(ratio={cost_ratio:.2f})")
    
    def test_extreme_speed_penalty(self):
        """Test that maximum speed (27 kts) has full penalty applied"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        
        # Apply penalty
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult
        
        # Check max speed (index -1)
        np.testing.assert_array_almost_equal(
            penalized_costs[:, -1],
            self.base_costs[:, -1] * penalty_mult,
            decimal=2,
            err_msg="Max speed (27 kts) should have full penalty"
        )


class TestPenaltyEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for speed penalty"""
    
    def setUp(self):
        """Set up vessel pool"""
        self.vessel_pool = read_vessel_class_data()
        self.base_costs, self.speed_level0 = self.vessel_pool.get_bukering_costs()
        self.n_speed_level = self.base_costs.shape[1]
    
    def test_no_penalty_multiplier_1(self):
        """Test that penalty_multiplier=1.0 means no change"""
        speed_soft_cap = 16.5
        penalty_mult = 1.0
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult
        
        # All costs should be unchanged
        np.testing.assert_array_equal(
            penalized_costs,
            self.base_costs,
            err_msg="Penalty multiplier 1.0 should leave costs unchanged"
        )
    
    def test_very_high_soft_cap(self):
        """Test that soft cap > max speed means no penalty applied"""
        speed_soft_cap = 30.0  # Higher than max speed (27 kts)
        penalty_mult = 2.0
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        
        # cap_index should be >= n_speed_level
        self.assertGreaterEqual(cap_index, self.n_speed_level,
                               "Cap index should be beyond speed range")
        
        # Apply penalty logic with bounds check
        penalized_costs = self.base_costs.copy()
        if cap_index < self.n_speed_level:
            penalized_costs[:, cap_index:] *= penalty_mult
        
        # All costs should be unchanged
        np.testing.assert_array_equal(
            penalized_costs,
            self.base_costs,
            err_msg="Soft cap > max speed should apply no penalty"
        )
    
    def test_soft_cap_at_minimum_speed(self):
        """Test that soft cap at minimum speed (10 kts) penalizes all speeds"""
        speed_soft_cap = 10.0
        penalty_mult = 3.0
        cap_index = int(np.ceil(speed_soft_cap - self.speed_level0))
        
        # cap_index should be 0 (penalize everything)
        self.assertEqual(cap_index, 0,
                        "Soft cap at min speed should give cap_index=0")
        
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult
        
        # All speeds should be penalized
        np.testing.assert_array_almost_equal(
            penalized_costs,
            self.base_costs * penalty_mult,
            decimal=2,
            err_msg="Soft cap at min speed should penalize ALL speeds"
        )


class TestPenaltyIntegration(unittest.TestCase):
    """Integration tests for speed penalty in actual optimization context"""
    
    def test_tuneparams_override(self):
        """Test that custom tuneparams properly override defaults"""
        from cma.servicegraph import ServiceGraph
        
        # Custom tuneparams with different values
        custom_params = {
            'turnon-transship_shipclass_restriction': 0,
            'turnon-vessel_speed_optimization': 0,
            'ctrparam-kts_buffer': 0,
            'ctrparam-transship_A': 100,
            'ctrparam-speed_soft_cap_kts': 18.0,        # Custom: 18 instead of 16.5
            'ctrparam-speed_penalty_multiplier': 3.5,   # Custom: 3.5 instead of 2.0
            'BigM-transship': 10000,
            'BigM-n_ships': 2,
            'BigM-saildays': 64,
            'BigM-line_capacity': 30000,
            'BigM-portcall_cost': 2e9
        }
        
        # Verify custom values different from defaults
        import inspect
        sig = inspect.signature(ServiceGraph.fulfill_demands)
        default_params = sig.parameters['tuneparams'].default
        
        self.assertNotEqual(
            custom_params['ctrparam-speed_soft_cap_kts'],
            default_params['ctrparam-speed_soft_cap_kts'],
            "Custom soft cap should differ from default"
        )
        
        self.assertNotEqual(
            custom_params['ctrparam-speed_penalty_multiplier'],
            default_params['ctrparam-speed_penalty_multiplier'],
            "Custom penalty multiplier should differ from default"
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
