"""Tests for simulator."""

import unittest
import os
from ddr5_power_tool.spec_parser import MemorySpec, MemoryPowerSpec, MemoryTimingSpec, ArchitectureSpec
from ddr5_power_tool.workload_parser import Workload, Command, CommandType
from ddr5_power_tool.simulator import Simulator


class TestSimulator(unittest.TestCase):
    """Test simulator."""
    
    def setUp(self):
        """Set up test fixtures."""
        power_spec = MemoryPowerSpec(
            idd0=51.0, idd2n=35.0, idd2p=25.0, idd3n=46.0, idd3p=15.0,
            idd4r=146.0, idd4w=120.0, idd5b=80.0, idd6=3.0,
            vdd=1.1, vddq=1.1, vddca=1.1
        )
        
        timing_spec = MemoryTimingSpec(
            tck=0.312, tras=32.0, trp=13.75, trcd=13.75, trfc=280.0
        )
        
        arch_spec = ArchitectureSpec(
            nbr_of_ranks=1, nbr_of_banks=4, nbr_of_columns=1024,
            nbr_of_rows=65536, width=64, burst_length=16, density=16
        )
        
        self.spec = MemorySpec(power=power_spec, timing=timing_spec, architecture=arch_spec)
    
    def test_simple_workload(self):
        """Test simple workload simulation."""
        commands = [
            Command(timestamp=0, command=CommandType.ACT, bank=0, rank=0, row=512),
            Command(timestamp=50, command=CommandType.RD, bank=0, rank=0, burst_length=16),
            Command(timestamp=150, command=CommandType.PRE, bank=0, rank=0),
            Command(timestamp=1000, command=CommandType.END_OF_SIMULATION)
        ]
        
        workload = Workload(commands=commands, metadata=None)
        simulator = Simulator(self.spec)
        result = simulator.simulate(workload)
        
        # Should have positive energy
        self.assertGreater(result.total_energy, 0)
        self.assertGreater(result.average_power, 0)
        self.assertGreater(result.simulation_time, 0)
        
        # Should have activation and read energy
        self.assertGreater(result.activation_energy, 0)
        self.assertGreater(result.read_energy, 0)
    
    def test_timing_violation_detection(self):
        """Test that timing violations are detected."""
        # Convert timestamps to account for tCK
        tck_cycles = 0.312  # ns per cycle
        # ACT at cycle 0 = 0 ns
        # PRE at cycle 10 = 10 * 0.312 = 3.12 ns (less than tRAS = 32 ns)
        commands = [
            Command(timestamp=0, command=CommandType.ACT, bank=0, rank=0, row=512),
            Command(timestamp=10, command=CommandType.PRE, bank=0, rank=0),  # Too early (tRAS violation)
            Command(timestamp=1000, command=CommandType.END_OF_SIMULATION)
        ]
        
        from ddr5_power_tool.workload_parser import WorkloadMetadata
        workload = Workload(commands=commands, metadata=WorkloadMetadata())
        simulator = Simulator(self.spec)
        result = simulator.simulate(workload)
        
        # Should have errors
        errors = simulator.get_errors()
        self.assertGreater(len(errors), 0, f"Expected timing violation errors, got: {errors}")
        self.assertTrue(any("tras" in error.lower() for error in errors), f"Expected tRAS violation in errors: {errors}")
    
    def test_refresh_command(self):
        """Test refresh command handling."""
        commands = [
            Command(timestamp=0, command=CommandType.REF, rank=0),
            Command(timestamp=10000, command=CommandType.END_OF_SIMULATION)
        ]
        
        from ddr5_power_tool.workload_parser import WorkloadMetadata
        workload = Workload(commands=commands, metadata=WorkloadMetadata())
        simulator = Simulator(self.spec)
        result = simulator.simulate(workload)
        
        # Should have refresh energy
        self.assertGreater(result.refresh_energy, 0)


if __name__ == '__main__':
    unittest.main()

