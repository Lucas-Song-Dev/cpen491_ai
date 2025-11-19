"""Integration tests using example files."""

import unittest
import os
from pathlib import Path
from ddr5_power_tool.spec_parser import MemorySpec
from ddr5_power_tool.workload_parser import Workload
from ddr5_power_tool.simulator import Simulator


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def test_example_ddr5_workload(self):
        """Test with example DDR5 spec and workload."""
        base_dir = Path(__file__).parent.parent
        spec_path = base_dir / "examples" / "ddr5_6400_spec.json"
        workload_path = base_dir / "examples" / "simple_workload.json"
        
        if not spec_path.exists() or not workload_path.exists():
            self.skipTest("Example files not found")
        
        spec = MemorySpec.from_json(str(spec_path))
        workload = Workload.from_json(str(workload_path))
        
        simulator = Simulator(spec)
        result = simulator.simulate(workload)
        
        # Verify results are reasonable
        self.assertGreater(result.total_energy, 0)
        self.assertGreater(result.average_power, 0)
        self.assertGreater(result.simulation_time, 0)
        
        # Verify breakdowns
        self.assertGreaterEqual(result.core_energy, 0)
        self.assertGreaterEqual(result.interface_energy, 0)
        
        # Total should equal sum of components
        total_breakdown = (
            result.activation_energy +
            result.read_energy +
            result.write_energy +
            result.precharge_energy +
            result.refresh_energy +
            result.background_active_energy +
            result.background_precharge_energy +
            result.powerdown_energy +
            result.termination_energy +
            result.dynamic_io_energy
        )
        
        # Allow small floating point differences
        self.assertAlmostEqual(result.total_energy, total_breakdown, delta=0.1)


if __name__ == '__main__':
    unittest.main()

