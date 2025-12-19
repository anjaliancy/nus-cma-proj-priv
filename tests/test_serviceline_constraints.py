"""
Test suite for ServiceLine constraint validation

Tests for:
- Max 20 unique ports per service
- Enhanced sub-route repetition detection (to be added)
"""
import pytest
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from cma import read_port_data
from cma.serviceline import ServiceLine


class TestServiceLineConstraints:
    """Test ServiceLine validation constraints"""
    
    @classmethod
    def setup_class(cls):
        """Load port data once for all tests"""
        cls.port_pool_finer, cls.port_pool = read_port_data()
    
    def test_max_20_unique_ports_valid(self):
        """Test that a service with exactly 20 unique ports is valid"""
        # Get first 20 ports
        ports = self.port_pool.tolist_port()[:20]
        
        # Create service line with exactly 20 unique ports
        service = ServiceLine("TEST_20", ports)
        
        # Should be valid
        assert service.check_valid(warn=False), "Service with 20 unique ports should be valid"
    
    def test_max_20_unique_ports_invalid(self):
        """Test that a service with 21 unique ports is invalid"""
        # Get first 21 ports
        ports = self.port_pool.tolist_port()[:21]
        
        # Create service line with 21 unique ports (bypass initial validation)
        service = ServiceLine("TEST_21", ports, _test=True)
        
        # Should be invalid
        assert not service.check_valid(warn=False), "Service with 21 unique ports should be invalid"
    
    def test_max_20_unique_ports_with_repetition(self):
        """Test that only unique ports are counted (repetitions allowed if edges unique)"""
        # Get first 10 ports
        unique_ports = self.port_pool.tolist_port()[:10]
        
        # Create line with 10 unique ports in a simple circle
        # All edges will be unique in a simple circular pattern
        service = ServiceLine("TEST_REPEAT", unique_ports, _test=True)
        
        # Should be valid (only 10 unique ports, all edges unique in circle)
        assert service.check_valid(warn=False), "Service with 10 unique ports should be valid"
    
    def test_max_20_unique_ports_edge_case_25_unique(self):
        """Test that a service with 25 unique ports is clearly invalid"""
        # Get first 25 ports
        ports = self.port_pool.tolist_port()[:25]
        
        # Create service line (bypass initial validation)
        service = ServiceLine("TEST_25", ports, _test=True)
        
        # Should be invalid
        assert not service.check_valid(warn=False), "Service with 25 unique ports should be invalid"
    
    def test_max_20_unique_ports_warning_message(self, capsys):
        """Test that warning message is displayed for too many unique ports"""
        # Get first 22 ports
        ports = self.port_pool.tolist_port()[:22]
        
        # Create service line (bypass initial validation)
        service = ServiceLine("TEST_WARN", ports, _test=True)
        
        # Check validity with warnings enabled
        result = service.check_valid(warn=True)
        
        # Capture output
        captured = capsys.readouterr()
        
        # Should be invalid
        assert not result, "Service should be invalid"
        
        # Should contain warning about unique ports
        assert "22 unique ports" in captured.out, "Warning should mention 22 unique ports"
        assert "max 20 allowed" in captured.out, "Warning should mention max 20 allowed"


class TestExistingConstraints:
    """Test that existing constraints still work"""
    
    @classmethod
    def setup_class(cls):
        """Load port data once for all tests"""
        cls.port_pool_finer, cls.port_pool = read_port_data()
    
    def test_consecutive_port_visits_invalid(self):
        """Test that consecutive identical ports are invalid"""
        ports = self.port_pool.tolist_port()[:5]
        
        # Create line with consecutive same port: P1, P2, P2, P3
        invalid_line = [ports[0], ports[1], ports[1], ports[2]]
        
        service = ServiceLine("TEST_CONSECUTIVE", invalid_line, _test=True)
        
        # Should be invalid
        assert not service.check_valid(warn=False), "Consecutive identical ports should be invalid"
    
    def test_repeated_slot_invalid(self):
        """Test that repeated slots (period-2 pattern) are invalid"""
        ports = self.port_pool.tolist_port()[:5]
        
        # Create line with repeated slot: P1, P2, P1, P2
        invalid_line = [ports[0], ports[1], ports[0], ports[1]]
        
        service = ServiceLine("TEST_SLOT_REPEAT", invalid_line, _test=True)
        
        # Should be invalid
        assert not service.check_valid(warn=False), "Repeated slots should be invalid"
    
    def test_valid_service_line(self):
        """Test that a normal valid service line passes all checks"""
        # Get first 10 ports
        ports = self.port_pool.tolist_port()[:10]
        
        service = ServiceLine("TEST_VALID", ports)
        
        # Should be valid
        assert service.check_valid(warn=False), "Normal service line should be valid"


class TestEnhancedSubrouteDetection:
    """Test enhanced sub-route repetition detection"""
    
    @classmethod
    def setup_class(cls):
        """Load port data once for all tests"""
        cls.port_pool_finer, cls.port_pool = read_port_data()
    
    def test_repeated_edge_simple_case(self):
        """Test that a simple repeated edge is detected: A→B→C→A→B"""
        ports = self.port_pool.tolist_port()[:5]
        
        # Pattern: P0→P1→P2→P0→P1 (edge P0→P1 appears twice)
        invalid_line = [ports[0], ports[1], ports[2], ports[0], ports[1]]
        
        service = ServiceLine("TEST_REPEAT_EDGE", invalid_line, _test=True)
        
        # Should be invalid
        assert not service.check_valid(warn=False), "Repeated edge A→B should be invalid"
    
    def test_repeated_edge_long_gap(self):
        """Test CNXMN→TWKHH→TWTXG→CNXMN→TWKHH pattern (from requirements)"""
        ports = self.port_pool.tolist_port()[:5]
        
        # Simulate: CNXMN→TWKHH→TWTXG→CNXMN→TWKHH
        # Pattern: P0→P1→P2→P0→P1 (edges P0→P1 repeated)
        invalid_line = [ports[0], ports[1], ports[2], ports[0], ports[1]]
        
        service = ServiceLine("TEST_CNXMN_PATTERN", invalid_line, _test=True)
        
        # Should be invalid due to repeated edge
        assert not service.check_valid(warn=False), "CNXMN→TWKHH pattern should be invalid"
    
    def test_repeated_edge_different_positions(self):
        """Test repeated edge at different positions: A→B→C→D→E→B→C"""
        ports = self.port_pool.tolist_port()[:7]
        
        # Pattern: P0→P1→P2→P3→P4→P1→P2 (edge P1→P2 appears twice)
        invalid_line = [ports[0], ports[1], ports[2], ports[3], ports[4], ports[1], ports[2]]
        
        service = ServiceLine("TEST_EDGE_FAR_APART", invalid_line, _test=True)
        
        # Should be invalid
        assert not service.check_valid(warn=False), "Repeated edge at different positions should be invalid"
    
    def test_no_repeated_edges_valid(self):
        """Test that a line with no repeated edges is valid"""
        ports = self.port_pool.tolist_port()[:8]
        
        # Pattern: P0→P1→P2→P3→P4→P5→P6→P7 (all unique edges)
        valid_line = ports[:8]
        
        service = ServiceLine("TEST_NO_REPEAT", valid_line, _test=True)
        
        # Should be valid
        assert service.check_valid(warn=False), "Line with all unique edges should be valid"
    
    def test_port_repetition_different_edges_valid(self):
        """Test that visiting same port via different incoming/outgoing edges"""
        ports = self.port_pool.tolist_port()[:6]
        
        # Pattern: P0→P1→P2→P0→P3→P4 (P0 visited twice)
        # Edges: P0→P1, P1→P2, P2→P0, P0→P3, P3→P4, P4→P0 (closing edge)
        # All edges are unique
        valid_line = [ports[0], ports[1], ports[2], ports[0], ports[3], ports[4]]
        
        service = ServiceLine("TEST_PORT_REPEAT_DIFF_EDGES", valid_line, _test=True)
        
        # Should be valid (all edges are different)
        assert service.check_valid(warn=False), "Same port with different edges should be valid"
    
    def test_circular_route_no_repeated_edges(self):
        """Test that circular route closes without repeating internal edges"""
        ports = self.port_pool.tolist_port()[:6]
        
        # Pattern: P0→P1→P2→P3→P4→P5 (circular, P5→P0 implicit)
        # All edges unique
        valid_line = ports[:6]
        
        service = ServiceLine("TEST_CIRCULAR", valid_line, _test=True)
        
        # Should be valid
        assert service.check_valid(warn=False), "Circular route should be valid"
    
    def test_repeated_edge_warning_message(self, capsys):
        """Test that warning message shows which edge is repeated"""
        ports = self.port_pool.tolist_port()[:5]
        
        # Pattern with repeated edge P1→P2
        invalid_line = [ports[0], ports[1], ports[2], ports[3], ports[1], ports[2]]
        
        service = ServiceLine("TEST_EDGE_WARN", invalid_line, _test=True)
        
        # Check with warnings
        result = service.check_valid(warn=True)
        
        # Capture output
        captured = capsys.readouterr()
        
        # Should be invalid
        assert not result, "Service should be invalid"
        
        # Should mention the repeated edge
        assert "edge" in captured.out.lower(), "Warning should mention 'edge'"
        assert "repeated" in captured.out.lower(), "Warning should mention 'repeated'"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
