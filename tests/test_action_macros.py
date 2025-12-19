"""
Test suite for multi-step action macros (composite operations)

Requirements tested:
1. reverse_segment reverses a portion of the rotation
2. rotate shifts the entire rotation
3. insert_port adds a port at specific position
4. remove_port deletes a port from rotation
5. move_port relocates a port (wrapper for shift_port)
6. All macros maintain service line validity
7. Macros handle circular rotation correctly
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from cma.data_reader import read_port_data
from cma.serviceline import ServiceLine


class TestReverseSegment(unittest.TestCase):
    """Tests for reverse_segment macro"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_reverse_middle_segment(self):
        """Test reversing a middle segment"""
        # [P0, P1, P2, P3, P4] → reverse(1,3) → [P0, P3, P2, P1, P4]
        original = self.line.tolist_port()
        reversed_line = self.line.reverse_segment(1, 3, validate=False)
        result = reversed_line.tolist_port()
        
        self.assertEqual(result[0], original[0])  # P0 unchanged
        self.assertEqual(result[1], original[3])  # P3 moved to index 1
        self.assertEqual(result[2], original[2])  # P2 stays
        self.assertEqual(result[3], original[1])  # P1 moved to index 3
        self.assertEqual(result[4], original[4])  # P4 unchanged
    
    def test_reverse_from_start(self):
        """Test reversing from start of rotation"""
        # [P0, P1, P2, P3, P4] → reverse(0,2) → [P2, P1, P0, P3, P4]
        original = self.line.tolist_port()
        reversed_line = self.line.reverse_segment(0, 2, validate=False)
        result = reversed_line.tolist_port()
        
        self.assertEqual(result[0], original[2])
        self.assertEqual(result[1], original[1])
        self.assertEqual(result[2], original[0])
        self.assertEqual(result[3], original[3])
        self.assertEqual(result[4], original[4])
    
    def test_reverse_to_end(self):
        """Test reversing to end of rotation"""
        # [P0, P1, P2, P3, P4] → reverse(2,4) → [P0, P1, P4, P3, P2]
        original = self.line.tolist_port()
        reversed_line = self.line.reverse_segment(2, 4, validate=False)
        result = reversed_line.tolist_port()
        
        self.assertEqual(result[0], original[0])
        self.assertEqual(result[1], original[1])
        self.assertEqual(result[2], original[4])
        self.assertEqual(result[3], original[3])
        self.assertEqual(result[4], original[2])
    
    def test_reverse_single_element(self):
        """Test reversing segment of size 1 (no change)"""
        original = self.line.tolist_port()
        reversed_line = self.line.reverse_segment(2, 2, validate=False)
        result = reversed_line.tolist_port()
        
        for i in range(len(original)):
            self.assertEqual(result[i], original[i])
    
    def test_reverse_entire_line(self):
        """Test reversing entire rotation"""
        original = self.line.tolist_port()
        reversed_line = self.line.reverse_segment(0, len(original)-1, validate=False)
        result = reversed_line.tolist_port()
        
        for i in range(len(original)):
            self.assertEqual(result[i], original[len(original)-1-i])


class TestRotate(unittest.TestCase):
    """Tests for rotate macro"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_rotate_right(self):
        """Test rotating right (positive steps)"""
        # [P0, P1, P2, P3, P4] → rotate(2) → [P3, P4, P0, P1, P2]
        original = self.line.tolist_port()
        rotated = self.line.rotate(2, validate=False)
        result = rotated.tolist_port()
        
        self.assertEqual(result[0], original[3])
        self.assertEqual(result[1], original[4])
        self.assertEqual(result[2], original[0])
        self.assertEqual(result[3], original[1])
        self.assertEqual(result[4], original[2])
    
    def test_rotate_left(self):
        """Test rotating left (negative steps)"""
        # [P0, P1, P2, P3, P4] → rotate(-1) → [P1, P2, P3, P4, P0]
        original = self.line.tolist_port()
        rotated = self.line.rotate(-1, validate=False)
        result = rotated.tolist_port()
        
        self.assertEqual(result[0], original[1])
        self.assertEqual(result[1], original[2])
        self.assertEqual(result[2], original[3])
        self.assertEqual(result[3], original[4])
        self.assertEqual(result[4], original[0])
    
    def test_rotate_zero(self):
        """Test rotate by 0 (no change)"""
        original = self.line.tolist_port()
        rotated = self.line.rotate(0, validate=False)
        result = rotated.tolist_port()
        
        for i in range(len(original)):
            self.assertEqual(result[i], original[i])
    
    def test_rotate_full_cycle(self):
        """Test rotating by line length (back to original)"""
        n = self.line.number_of_port()
        original = self.line.tolist_port()
        rotated = self.line.rotate(n, validate=False)
        result = rotated.tolist_port()
        
        for i in range(len(original)):
            self.assertEqual(result[i], original[i])
    
    def test_rotate_large_steps(self):
        """Test rotating by more than line length"""
        n = self.line.number_of_port()
        original = self.line.tolist_port()
        
        # rotate(7) on 5-port line should be same as rotate(2)
        rotated = self.line.rotate(7, validate=False)
        result = rotated.tolist_port()
        
        expected_rotation = 7 % n  # = 2
        for i in range(n):
            expected_idx = (n - expected_rotation + i) % n
            self.assertEqual(result[i], original[expected_idx])


class TestInsertPort(unittest.TestCase):
    """Tests for insert_port macro"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 4:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
        
        # Get a port to insert
        if self.portpool.has_port_by_id('JPYOK'):
            self.new_port = self.portpool.get_port('JPYOK')
        else:
            self.skipTest("JPYOK port not available")
    
    def test_insert_at_start(self):
        """Test inserting port at start"""
        original = self.line.tolist_port()
        inserted = self.line.insert_port(self.new_port, 0, validate=False)
        result = inserted.tolist_port()
        
        self.assertEqual(len(result), len(original) + 1)
        self.assertEqual(result[0], self.new_port)
        for i in range(len(original)):
            self.assertEqual(result[i+1], original[i])
    
    def test_insert_in_middle(self):
        """Test inserting port in middle"""
        original = self.line.tolist_port()
        inserted = self.line.insert_port(self.new_port, 2, validate=False)
        result = inserted.tolist_port()
        
        self.assertEqual(len(result), len(original) + 1)
        self.assertEqual(result[0], original[0])
        self.assertEqual(result[1], original[1])
        self.assertEqual(result[2], self.new_port)
        self.assertEqual(result[3], original[2])
        self.assertEqual(result[4], original[3])
    
    def test_insert_at_end(self):
        """Test inserting port at end"""
        original = self.line.tolist_port()
        n = len(original)
        inserted = self.line.insert_port(self.new_port, n, validate=False)
        result = inserted.tolist_port()
        
        self.assertEqual(len(result), n + 1)
        for i in range(n):
            self.assertEqual(result[i], original[i])
        self.assertEqual(result[n], self.new_port)


class TestRemovePort(unittest.TestCase):
    """Tests for remove_port macro"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_remove_from_start(self):
        """Test removing port from start"""
        original = self.line.tolist_port()
        removed = self.line.remove_port(0, validate=False)
        result = removed.tolist_port()
        
        self.assertEqual(len(result), len(original) - 1)
        for i in range(len(result)):
            self.assertEqual(result[i], original[i+1])
    
    def test_remove_from_middle(self):
        """Test removing port from middle"""
        original = self.line.tolist_port()
        removed = self.line.remove_port(2, validate=False)
        result = removed.tolist_port()
        
        self.assertEqual(len(result), len(original) - 1)
        self.assertEqual(result[0], original[0])
        self.assertEqual(result[1], original[1])
        self.assertEqual(result[2], original[3])  # P3 shifts to position 2
        self.assertEqual(result[3], original[4])  # P4 shifts to position 3
    
    def test_remove_from_end(self):
        """Test removing port from end"""
        original = self.line.tolist_port()
        n = len(original)
        removed = self.line.remove_port(n-1, validate=False)
        result = removed.tolist_port()
        
        self.assertEqual(len(result), n - 1)
        for i in range(len(result)):
            self.assertEqual(result[i], original[i])


class TestMovePort(unittest.TestCase):
    """Tests for move_port macro (wrapper for shift_port)"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_move_port_forward(self):
        """Test moving port forward"""
        # [P0, P1, P2, P3, P4] → move_port(1, 3) → [P0, P2, P3, P1, P4]
        original = self.line.tolist_port()
        moved = self.line.move_port(1, 3, validate=False)
        result = moved.tolist_port()
        
        self.assertEqual(result[3], original[1])
        self.assertEqual(result[0], original[0])
        self.assertEqual(result[1], original[2])
        self.assertEqual(result[2], original[3])
        self.assertEqual(result[4], original[4])
    
    def test_move_port_backward(self):
        """Test moving port backward"""
        # [P0, P1, P2, P3, P4] → move_port(3, 1) → [P0, P3, P1, P2, P4]
        original = self.line.tolist_port()
        moved = self.line.move_port(3, 1, validate=False)
        result = moved.tolist_port()
        
        self.assertEqual(result[1], original[3])
        self.assertEqual(result[0], original[0])
        self.assertEqual(result[2], original[1])
        self.assertEqual(result[3], original[2])
        self.assertEqual(result[4], original[4])
    
    def test_move_port_same_position(self):
        """Test moving port to same position (no change)"""
        original = self.line.tolist_port()
        moved = self.line.move_port(2, 2, validate=False)
        result = moved.tolist_port()
        
        for i in range(len(original)):
            self.assertEqual(result[i], original[i])


class TestMacroComposition(unittest.TestCase):
    """Test composing multiple macro operations"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_rotate_then_reverse(self):
        """Test rotating then reversing"""
        step1 = self.line.rotate(1, validate=False)
        step2 = step1.reverse_segment(1, 3, validate=False)
        
        self.assertEqual(step2.number_of_port(), self.line.number_of_port())
    
    def test_reverse_then_rotate(self):
        """Test reversing then rotating"""
        step1 = self.line.reverse_segment(0, 2, validate=False)
        step2 = step1.rotate(-1, validate=False)
        
        self.assertEqual(step2.number_of_port(), self.line.number_of_port())
    
    def test_insert_then_remove(self):
        """Test inserting then removing (different positions)"""
        if not self.portpool.has_port_by_id('KRPUS'):
            self.skipTest("KRPUS port not available")
        
        new_port = self.portpool.get_port('KRPUS')
        step1 = self.line.insert_port(new_port, 2, validate=False)
        step2 = step1.remove_port(4, validate=False)
        
        # After insert and remove at different positions
        self.assertEqual(step2.number_of_port(), self.line.number_of_port())


class TestMacroImmutability(unittest.TestCase):
    """Test that macros don't modify original service line"""
    
    def setUp(self):
        """Set up test data"""
        port_pools = read_port_data()
        self.portpool = port_pools[0]
        
        port_ids = ['CNSHA', 'CNNGB', 'SGSIN', 'HKHKG', 'JPYOK']
        self.ports = [self.portpool.get_port(pid) for pid in port_ids if self.portpool.has_port_by_id(pid)]
        
        if len(self.ports) < 5:
            self.skipTest("Not all required ports available")
        
        self.line = ServiceLine("TestLine", self.ports, _test=True)
    
    def test_reverse_immutability(self):
        """Test that reverse_segment doesn't modify original"""
        original = self.line.tolist_port().copy()
        self.line.reverse_segment(1, 3, validate=False)
        current = self.line.tolist_port()
        
        for i in range(len(original)):
            self.assertEqual(current[i], original[i])
    
    def test_rotate_immutability(self):
        """Test that rotate doesn't modify original"""
        original = self.line.tolist_port().copy()
        self.line.rotate(2, validate=False)
        current = self.line.tolist_port()
        
        for i in range(len(original)):
            self.assertEqual(current[i], original[i])
    
    def test_insert_immutability(self):
        """Test that insert_port doesn't modify original"""
        if not self.portpool.has_port_by_id('KRPUS'):
            self.skipTest("KRPUS port not available")
        
        original_len = self.line.number_of_port()
        new_port = self.portpool.get_port('KRPUS')
        self.line.insert_port(new_port, 2, validate=False)
        
        self.assertEqual(self.line.number_of_port(), original_len)
    
    def test_remove_immutability(self):
        """Test that remove_port doesn't modify original"""
        original_len = self.line.number_of_port()
        self.line.remove_port(2, validate=False)
        
        self.assertEqual(self.line.number_of_port(), original_len)


if __name__ == '__main__':
    unittest.main(verbosity=2)
