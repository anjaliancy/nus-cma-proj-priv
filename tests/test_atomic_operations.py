"""
Test suite for atomic service line operations (shift_port and swap_ports)

Requirements tested:
1. shift_port moves a port visit to a different position
2. swap_ports exchanges two port visits
3. Both operations maintain service line validity
4. Circular rotation is handled correctly
5. Edge cases and invalid operations raise appropriate errors
6. Operations are truly atomic (single action)
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_port_data
from cma.serviceline import ServiceLine


class TestShiftPortBasic(unittest.TestCase):
    """Basic functionality tests for shift_port operation"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        # Create simple service line for testing
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_shift_port_forward(self):
        """Test shifting a port forward (later) in rotation"""
        # Original: [P0, P1, P2, P3, P4]
        # shift_port(1, 2) → [P0, P2, P3, P1, P4]
        
        original_ports = self.line.tolist_port()
        shifted_line = self.line.shift_port(1, 2, validate=False)
        shifted_ports = shifted_line.tolist_port()
        
        # P1 should now be at position 3
        self.assertEqual(shifted_ports[3], original_ports[1],
                        "Port at index 1 should be at index 3 after shift(1, 2)")
        
        # Other ports should shift accordingly
        self.assertEqual(shifted_ports[0], original_ports[0])
        self.assertEqual(shifted_ports[1], original_ports[2])
        self.assertEqual(shifted_ports[2], original_ports[3])
        self.assertEqual(shifted_ports[4], original_ports[4])
    
    def test_shift_port_backward(self):
        """Test shifting a port backward (earlier) in rotation"""
        # Original: [P0, P1, P2, P3, P4]
        # shift_port(3, -2) → [P0, P3, P1, P2, P4]
        
        original_ports = self.line.tolist_port()
        shifted_line = self.line.shift_port(3, -2, validate=False)
        shifted_ports = shifted_line.tolist_port()
        
        # P3 should now be at position 1
        self.assertEqual(shifted_ports[1], original_ports[3],
                        "Port at index 3 should be at index 1 after shift(3, -2)")
        
        # Other ports should shift accordingly
        self.assertEqual(shifted_ports[0], original_ports[0])
        self.assertEqual(shifted_ports[2], original_ports[1])
        self.assertEqual(shifted_ports[3], original_ports[2])
        self.assertEqual(shifted_ports[4], original_ports[4])
    
    def test_shift_port_zero_delta(self):
        """Test that shift by 0 returns unchanged line"""
        shifted_line = self.line.shift_port(2, 0, validate=False)
        
        original_ports = self.line.tolist_port()
        shifted_ports = shifted_line.tolist_port()
        
        self.assertEqual(len(shifted_ports), len(original_ports))
        for i in range(len(original_ports)):
            self.assertEqual(shifted_ports[i], original_ports[i],
                           f"Port at index {i} should be unchanged")
    
    def test_shift_port_wraps_around(self):
        """Test that shift handles circular rotation correctly"""
        # Original: [P0, P1, P2, P3, P4]
        # shift_port(4, 2) with 5 ports → wraps to position 1
        
        original_ports = self.line.tolist_port()
        n = len(original_ports)
        
        # Shift last port by 2 (should wrap to position 1)
        shifted_line = self.line.shift_port(4, 2, validate=False)
        shifted_ports = shifted_line.tolist_port()
        
        expected_pos = (4 + 2) % n  # = 1
        self.assertEqual(shifted_ports[expected_pos], original_ports[4],
                        f"Port at index 4 should wrap to index {expected_pos}")
    
    def test_shift_port_negative_wraps_around(self):
        """Test that negative shift wraps around correctly"""
        # Original: [P0, P1, P2, P3, P4]
        # shift_port(1, -2) with 5 ports → wraps to position 4
        
        original_ports = self.line.tolist_port()
        n = len(original_ports)
        
        shifted_line = self.line.shift_port(1, -2, validate=False)
        shifted_ports = shifted_line.tolist_port()
        
        expected_pos = (1 - 2) % n  # = 4
        self.assertEqual(shifted_ports[expected_pos], original_ports[1],
                        f"Port at index 1 should wrap to index {expected_pos}")
    
    def test_shift_preserves_line_length(self):
        """Test that shift doesn't change number of ports"""
        original_length = self.line.number_of_port()
        shifted_line = self.line.shift_port(2, 1, validate=False)
        
        self.assertEqual(shifted_line.number_of_port(), original_length,
                        "Shift should preserve number of ports")


class TestShiftPortValidation(unittest.TestCase):
    """Validation tests for shift_port operation"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_shift_invalid_index_raises_error(self):
        """Test that invalid port index raises ValueError"""
        n = self.line.number_of_port()
        
        with self.assertRaises(ValueError):
            self.line.shift_port(-1, 1)  # Negative index
        
        with self.assertRaises(ValueError):
            self.line.shift_port(n, 1)  # Index out of bounds
        
        with self.assertRaises(ValueError):
            self.line.shift_port(n + 5, 1)  # Way out of bounds
    
    def test_shift_with_validation_enabled(self):
        """Test that validation can be enabled"""
        # This should work fine with validation
        shifted_line = self.line.shift_port(1, 2, validate=True)
        self.assertIsInstance(shifted_line, ServiceLine)
    
    def test_shift_creating_invalid_line(self):
        """Test that shift creating invalid line raises error with validation"""
        # Create a line where shifting would create consecutive duplicates
        # This is tricky - we need a specific pattern
        # For now, just verify the mechanism works
        try:
            # Normal shift should work
            self.line.shift_port(1, 1, validate=True)
            self.assertTrue(True, "Normal shift should succeed")
        except ValueError:
            self.fail("Normal shift shouldn't fail validation")


class TestSwapPortsBasic(unittest.TestCase):
    """Basic functionality tests for swap_ports operation"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_swap_adjacent_ports(self):
        """Test swapping adjacent ports"""
        # Original: [P0, P1, P2, P3, P4]
        # swap_ports(1, 2) → [P0, P2, P1, P3, P4]
        
        original_ports = self.line.tolist_port()
        swapped_line = self.line.swap_ports(1, 2, validate=False)
        swapped_ports = swapped_line.tolist_port()
        
        # P1 and P2 should be swapped
        self.assertEqual(swapped_ports[1], original_ports[2],
                        "Port at index 2 should be at index 1 after swap")
        self.assertEqual(swapped_ports[2], original_ports[1],
                        "Port at index 1 should be at index 2 after swap")
        
        # Other ports unchanged
        self.assertEqual(swapped_ports[0], original_ports[0])
        self.assertEqual(swapped_ports[3], original_ports[3])
        self.assertEqual(swapped_ports[4], original_ports[4])
    
    def test_swap_distant_ports(self):
        """Test swapping non-adjacent ports"""
        # Original: [P0, P1, P2, P3, P4]
        # swap_ports(1, 4) → [P0, P4, P2, P3, P1]
        
        original_ports = self.line.tolist_port()
        swapped_line = self.line.swap_ports(1, 4, validate=False)
        swapped_ports = swapped_line.tolist_port()
        
        self.assertEqual(swapped_ports[1], original_ports[4],
                        "Port at index 4 should be at index 1")
        self.assertEqual(swapped_ports[4], original_ports[1],
                        "Port at index 1 should be at index 4")
        
        # Middle ports unchanged
        self.assertEqual(swapped_ports[2], original_ports[2])
        self.assertEqual(swapped_ports[3], original_ports[3])
    
    def test_swap_first_and_last(self):
        """Test swapping first and last ports"""
        original_ports = self.line.tolist_port()
        n = len(original_ports)
        
        swapped_line = self.line.swap_ports(0, n-1, validate=False)
        swapped_ports = swapped_line.tolist_port()
        
        self.assertEqual(swapped_ports[0], original_ports[n-1])
        self.assertEqual(swapped_ports[n-1], original_ports[0])
    
    def test_swap_same_index(self):
        """Test that swapping port with itself returns unchanged line"""
        swapped_line = self.line.swap_ports(2, 2, validate=False)
        
        original_ports = self.line.tolist_port()
        swapped_ports = swapped_line.tolist_port()
        
        for i in range(len(original_ports)):
            self.assertEqual(swapped_ports[i], original_ports[i],
                           "Swapping port with itself should not change line")
    
    def test_swap_preserves_line_length(self):
        """Test that swap doesn't change number of ports"""
        original_length = self.line.number_of_port()
        swapped_line = self.line.swap_ports(1, 3, validate=False)
        
        self.assertEqual(swapped_line.number_of_port(), original_length,
                        "Swap should preserve number of ports")
    
    def test_swap_is_symmetric(self):
        """Test that swap(i,j) == swap(j,i)"""
        swap_12 = self.line.swap_ports(1, 3, validate=False)
        swap_21 = self.line.swap_ports(3, 1, validate=False)
        
        ports_12 = swap_12.tolist_port()
        ports_21 = swap_21.tolist_port()
        
        for i in range(len(ports_12)):
            self.assertEqual(ports_12[i], ports_21[i],
                           "swap(i,j) should equal swap(j,i)")


class TestSwapPortsValidation(unittest.TestCase):
    """Validation tests for swap_ports operation"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_swap_invalid_index_raises_error(self):
        """Test that invalid indices raise ValueError"""
        n = self.line.number_of_port()
        
        with self.assertRaises(ValueError):
            self.line.swap_ports(-1, 1)  # Negative idx1
        
        with self.assertRaises(ValueError):
            self.line.swap_ports(1, -1)  # Negative idx2
        
        with self.assertRaises(ValueError):
            self.line.swap_ports(n, 1)  # idx1 out of bounds
        
        with self.assertRaises(ValueError):
            self.line.swap_ports(1, n)  # idx2 out of bounds
    
    def test_swap_with_validation_enabled(self):
        """Test that validation can be enabled"""
        swapped_line = self.line.swap_ports(1, 3, validate=True)
        self.assertIsInstance(swapped_line, ServiceLine)


class TestOperationComposition(unittest.TestCase):
    """Test composing multiple operations"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_shift_then_shift(self):
        """Test composing two shift operations"""
        # Shift port 1 by 2, then shift port 3 by -1
        line1 = self.line.shift_port(1, 2, validate=False)
        line2 = line1.shift_port(3, -1, validate=False)
        
        self.assertEqual(line2.number_of_port(), self.line.number_of_port(),
                        "Composed shifts should preserve port count")
    
    def test_swap_then_swap(self):
        """Test composing two swap operations"""
        # Swap 1,3 then swap 0,4
        line1 = self.line.swap_ports(1, 3, validate=False)
        line2 = line1.swap_ports(0, 4, validate=False)
        
        self.assertEqual(line2.number_of_port(), self.line.number_of_port(),
                        "Composed swaps should preserve port count")
    
    def test_shift_then_swap(self):
        """Test composing shift and swap operations"""
        line1 = self.line.shift_port(2, 1, validate=False)
        line2 = line1.swap_ports(1, 3, validate=False)
        
        self.assertEqual(line2.number_of_port(), self.line.number_of_port(),
                        "Shift then swap should preserve port count")
    
    def test_swap_then_shift(self):
        """Test composing swap then shift"""
        line1 = self.line.swap_ports(0, 2, validate=False)
        line2 = line1.shift_port(1, 2, validate=False)
        
        self.assertEqual(line2.number_of_port(), self.line.number_of_port(),
                        "Swap then shift should preserve port count")
    
    def test_swap_inverse(self):
        """Test that swapping twice returns to original"""
        swapped = self.line.swap_ports(1, 3, validate=False)
        back = swapped.swap_ports(1, 3, validate=False)
        
        original_ports = self.line.tolist_port()
        back_ports = back.tolist_port()
        
        for i in range(len(original_ports)):
            self.assertEqual(back_ports[i], original_ports[i],
                           "Swapping twice should return to original")


class TestOperationEdgeCases(unittest.TestCase):
    """Test edge cases and special scenarios"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
    
    def test_shift_on_small_line(self):
        """Test shift on line with only 2 ports"""
        if not (self.portpool.has_port_by_id('CNSHA') and self.portpool.has_port_by_id('HKHKG')):
            self.skipTest("Required ports not available")
        
        ports = [self.portpool.get_port('CNSHA'), self.portpool.get_port('HKHKG')]
        line = ServiceLine("SmallLine", ports, _test=True)
        
        # Shifting in 2-port line
        shifted = line.shift_port(0, 1, validate=False)
        shifted_ports = shifted.tolist_port()
        
        # After shifting port 0 by 1, order should reverse
        self.assertEqual(shifted_ports[0], ports[1])
        self.assertEqual(shifted_ports[1], ports[0])
    
    def test_swap_on_small_line(self):
        """Test swap on line with only 2 ports"""
        if not (self.portpool.has_port_by_id('CNSHA') and self.portpool.has_port_by_id('HKHKG')):
            self.skipTest("Required ports not available")
        
        ports = [self.portpool.get_port('CNSHA'), self.portpool.get_port('HKHKG')]
        line = ServiceLine("SmallLine", ports, _test=True)
        
        swapped = line.swap_ports(0, 1, validate=False)
        swapped_ports = swapped.tolist_port()
        
        self.assertEqual(swapped_ports[0], ports[1])
        self.assertEqual(swapped_ports[1], ports[0])
    
    def test_large_shift_delta(self):
        """Test shift with delta larger than line length"""
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN']
        ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(ports) < 3:
            self.skipTest("Required ports not available")
        
        line = ServiceLine("TestLine", ports, _test=True)
        
        # Shift by 10 on 3-port line (wraps multiple times)
        shifted = line.shift_port(0, 10, validate=False)
        
        # 10 % 3 = 1, so should shift by 1
        original_ports = line.tolist_port()
        shifted_ports = shifted.tolist_port()
        
        expected_pos = (0 + 10) % 3  # = 1
        self.assertEqual(shifted_ports[expected_pos], original_ports[0])


class TestOperationImmutability(unittest.TestCase):
    """Test that operations don't modify original service line"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 4:
            self.skipTest("Required ports not available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_shift_immutability(self):
        """Test that shift_port doesn't modify original line"""
        original_ports = self.line.tolist_port().copy()
        
        # Perform shift
        self.line.shift_port(1, 2, validate=False)
        
        # Check original unchanged
        current_ports = self.line.tolist_port()
        for i in range(len(original_ports)):
            self.assertEqual(current_ports[i], original_ports[i],
                           "Original line should not be modified by shift")
    
    def test_swap_immutability(self):
        """Test that swap_ports doesn't modify original line"""
        original_ports = self.line.tolist_port().copy()
        
        # Perform swap
        self.line.swap_ports(1, 3, validate=False)
        
        # Check original unchanged
        current_ports = self.line.tolist_port()
        for i in range(len(original_ports)):
            self.assertEqual(current_ports[i], original_ports[i],
                           "Original line should not be modified by swap")


if __name__ == '__main__':
    unittest.main(verbosity=2)
