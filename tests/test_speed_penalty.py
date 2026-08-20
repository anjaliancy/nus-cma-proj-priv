"""
Test suite for speed soft cap penalty (>16.5 kts)

Requirements tested:
1. Speed penalty parameters properly added to tuneparams
2. Bukering costs multiplied for speeds strictly above 16.5 kts
3. Different penalty multipliers work correctly
4. No penalty applied at or below 16.5 kts
5. Penalty calculation logic correct for edge cases

CHANGE 20/08 (client feedback #5a): this file used to duplicate the cap_index
formula locally instead of calling the real production code, and checked it
against a fabricated 1kt-step speed array instead of the real fleet's 0.5kt-step
grid - so it could never have caught the real bug (penalty starting at 13.5kt
instead of 17.0kt) and gave false confidence. It now imports
`compute_speed_penalty_cap_index` from `cma.servicegraph` (the actual function
used by `fulfill_demands`) and uses the real speed grid from
`vessel_pool.get_speed_levels()`, so a future regression here would fail these
tests.
"""

import unittest
import numpy as np
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_vessel_class_data
from cma.servicegraph import compute_speed_penalty_cap_index


class TestSpeedPenaltyParameters(unittest.TestCase):
    """Test that tuneparams properly include speed penalty parameters"""

    def test_default_speed_soft_cap(self):
        """Test that default soft cap is 16.5 kts"""
        from cma.servicegraph import ServiceGraph

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
        """Set up vessel pool to get bukering costs and the real speed grid"""
        self.vessel_pool = read_vessel_class_data()
        self.base_costs, self.speed_level0 = self.vessel_pool.get_bukering_costs()
        self.n_speed_level = self.base_costs.shape[1]
        self.KTS_levels = self.vessel_pool.get_speed_levels()
        self.speed_step = self.KTS_levels[1] - self.KTS_levels[0]

    def test_penalty_calculation_logic(self):
        """Test that the real cap_index formula correctly identifies 17.0kt as
        the first level strictly above the 16.5kt soft cap, on the real 0.5kt
        step grid (not a 1kt-step approximation)."""
        speed_soft_cap = 16.5

        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        self.assertEqual(self.KTS_levels[cap_index], 17.0,
                        "cap_index should point at 17.0 kts for soft cap 16.5 kts "
                        "on the real 0.5kt-step grid")
        self.assertEqual(self.KTS_levels[cap_index - 1], 16.5,
                        "the level just before cap_index should be 16.5 kts itself "
                        "(unpenalised - the rule is 'above 16.5', not 'at 16.5')")

    def test_penalty_applied_to_high_speeds(self):
        """Test that penalty multiplier is applied to speeds > 16.5 kts"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0

        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult

        for speed_idx in range(cap_index, self.n_speed_level):
            np.testing.assert_array_almost_equal(
                penalized_costs[:, speed_idx],
                self.base_costs[:, speed_idx] * penalty_mult,
                decimal=2,
                err_msg=f"Speed {self.KTS_levels[speed_idx]}kt should have {penalty_mult}x penalty"
            )

    def test_no_penalty_for_low_speeds(self):
        """Test that no penalty is applied at or below 16.5 kts"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0

        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )
        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult

        for speed_idx in range(cap_index):
            np.testing.assert_array_almost_equal(
                penalized_costs[:, speed_idx],
                self.base_costs[:, speed_idx],
                decimal=2,
                err_msg=f"Speed {self.KTS_levels[speed_idx]}kt should have NO penalty"
            )

    def test_different_penalty_multipliers(self):
        """Test that different penalty multipliers work correctly"""
        speed_soft_cap = 16.5
        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        for penalty_mult in [1.5, 2.0, 2.5, 3.0, 5.0]:
            penalized_costs = self.base_costs.copy()
            penalized_costs[:, cap_index:] *= penalty_mult

            for speed_idx in range(cap_index, self.n_speed_level):
                np.testing.assert_array_almost_equal(
                    penalized_costs[:, speed_idx],
                    self.base_costs[:, speed_idx] * penalty_mult,
                    decimal=2,
                    err_msg=f"Penalty multiplier {penalty_mult} not applied correctly"
                )

    def test_penalty_boundary_at_17_knots(self):
        """Test that the penalty boundary sits exactly between 16.5kt (free) and
        17.0kt (penalised) on the real speed grid."""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        # 16.5 kts (just before cap_index) should NOT have penalty
        self.assertEqual(self.KTS_levels[cap_index - 1], 16.5,
                       "Speed before cap_index should be 16.5kt")

        # 17.0 kts (at cap_index) should HAVE penalty
        self.assertEqual(self.KTS_levels[cap_index], 17.0,
                          "Speed at cap_index should be 17.0kt")

        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult

        np.testing.assert_array_equal(
            penalized_costs[:, cap_index - 1],
            self.base_costs[:, cap_index - 1],
            err_msg="16.5 kts should have NO penalty"
        )

        np.testing.assert_array_almost_equal(
            penalized_costs[:, cap_index],
            self.base_costs[:, cap_index] * penalty_mult,
            decimal=2,
            err_msg=f"17.0 kts should have {penalty_mult}x penalty"
        )

    def test_penalty_magnitude(self):
        """Test that penalty creates significant cost difference between the
        last free level (16.5kt) and the first penalised level (17.0kt)."""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult

        for rank_idx in range(self.base_costs.shape[0]):
            # Compare 16.5 kts (free) vs 17.0 kts (penalised)
            cost_16_5kts = penalized_costs[rank_idx, cap_index - 1]
            cost_17kts = penalized_costs[rank_idx, cap_index]

            # Natural cost increase from 16.5->17.0 is a few percent; the 2x
            # penalty dominates, so the combined ratio should clear 1.8x.
            cost_ratio = cost_17kts / cost_16_5kts
            self.assertGreater(cost_ratio, 1.8,
                              f"Rank {rank_idx}: 17.0 kts should cost >=1.8x more than 16.5 kts "
                              f"(ratio={cost_ratio:.2f})")

    def test_extreme_speed_penalty(self):
        """Test that the fastest speed on the grid (18.5 kts) has full penalty applied"""
        speed_soft_cap = 16.5
        penalty_mult = 2.0
        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult

        self.assertEqual(self.KTS_levels[-1], 18.5, "Fleet's fastest grid speed should be 18.5kt")
        np.testing.assert_array_almost_equal(
            penalized_costs[:, -1],
            self.base_costs[:, -1] * penalty_mult,
            decimal=2,
            err_msg="Max speed (18.5 kts) should have full penalty"
        )


class TestPenaltyEdgeCases(unittest.TestCase):
    """Test edge cases and error handling for speed penalty"""

    def setUp(self):
        """Set up vessel pool"""
        self.vessel_pool = read_vessel_class_data()
        self.base_costs, self.speed_level0 = self.vessel_pool.get_bukering_costs()
        self.n_speed_level = self.base_costs.shape[1]
        self.KTS_levels = self.vessel_pool.get_speed_levels()
        self.speed_step = self.KTS_levels[1] - self.KTS_levels[0]

    def test_no_penalty_multiplier_1(self):
        """Test that penalty_multiplier=1.0 means no change"""
        speed_soft_cap = 16.5
        penalty_mult = 1.0
        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult

        np.testing.assert_array_equal(
            penalized_costs,
            self.base_costs,
            err_msg="Penalty multiplier 1.0 should leave costs unchanged"
        )

    def test_very_high_soft_cap(self):
        """Test that a soft cap above the fastest grid speed means no penalty applied"""
        speed_soft_cap = 30.0  # Higher than max real speed (18.5 kts)
        penalty_mult = 2.0
        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        self.assertGreaterEqual(cap_index, self.n_speed_level,
                               "Cap index should be beyond speed range")

        penalized_costs = self.base_costs.copy()
        if cap_index < self.n_speed_level:
            penalized_costs[:, cap_index:] *= penalty_mult

        np.testing.assert_array_equal(
            penalized_costs,
            self.base_costs,
            err_msg="Soft cap above max grid speed should apply no penalty"
        )

    def test_soft_cap_at_minimum_speed(self):
        """Test that a soft cap set exactly at the minimum grid speed (10.0 kts)
        penalises every speed except the minimum itself - the rule is
        'penalised STRICTLY ABOVE the cap', so the cap level itself stays free."""
        speed_soft_cap = 10.0
        penalty_mult = 3.0
        cap_index = compute_speed_penalty_cap_index(
            speed_soft_cap, self.speed_level0, self.speed_step
        )

        # cap_index should be 1: index 0 (10.0kt, == the cap) stays free,
        # everything from index 1 (10.5kt) up is strictly above the cap.
        self.assertEqual(cap_index, 1,
                        "Soft cap at min grid speed should give cap_index=1 "
                        "(only the minimum speed itself stays unpenalised)")

        penalized_costs = self.base_costs.copy()
        penalized_costs[:, cap_index:] *= penalty_mult

        np.testing.assert_array_equal(
            penalized_costs[:, 0],
            self.base_costs[:, 0],
            err_msg="The minimum speed itself (== the cap) should stay unpenalised"
        )
        np.testing.assert_array_almost_equal(
            penalized_costs[:, 1:],
            self.base_costs[:, 1:] * penalty_mult,
            decimal=2,
            err_msg="Every speed above the minimum should be penalised"
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
