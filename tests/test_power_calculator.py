"""Tests for power calculator."""

import unittest
from ddr5_power_tool.spec_parser import MemorySpec, MemoryPowerSpec, MemoryTimingSpec, ArchitectureSpec
from ddr5_power_tool.state_machine import DRAMStateMachine
from ddr5_power_tool.power_calculator import PowerCalculator
from ddr5_power_tool.workload_parser import CommandType


class TestPowerCalculator(unittest.TestCase):
    """Test power calculator."""
    
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
        self.state_machine = DRAMStateMachine(self.spec)
        self.calculator = PowerCalculator(self.spec, self.state_machine)
    
    def test_read_power_calculation(self):
        """Test read power calculation."""
        duration_ns = 10.0
        energy = self.calculator.calculate_read_power(duration_ns, burst_length=16)
        
        # Should be positive
        self.assertGreater(energy, 0)
        
        # Should include both core and I/O power
        # I_DD4R - I_DD3N = 146 - 46 = 100 mA
        # Power = 100 mA * 1.1 V = 110 mW
        # Energy = 110 mW * 10 ns / 1000 = 1.1 nJ (core only, I/O adds more)
        self.assertGreater(energy, 1.0)
    
    def test_write_power_calculation(self):
        """Test write power calculation."""
        duration_ns = 10.0
        energy = self.calculator.calculate_write_power(duration_ns, burst_length=16)
        
        self.assertGreater(energy, 0)
    
    def test_refresh_power_calculation(self):
        """Test refresh power calculation."""
        duration_ns = 280.0  # tRFC
        energy = self.calculator.calculate_refresh_power(duration_ns)
        
        # I_DD5B = 80 mA, V_DD = 1.1 V
        # Power = 80 * 1.1 = 88 mW
        # Energy = 88 * 280 / 1000 = 24.64 nJ
        expected = 80.0 * 1.1 * 280.0 / 1000.0
        self.assertAlmostEqual(energy, expected, places=2)
    
    def test_background_power_calculation(self):
        """Test background power calculation."""
        active_time = 100.0  # ns
        precharge_time = 200.0  # ns
        
        bg_active, bg_precharge = self.calculator.calculate_background_power(
            active_time, precharge_time
        )
        
        # Active: I_DD3N = 46 mA, V_DD = 1.1 V
        # Power = 46 * 1.1 = 50.6 mW
        # Energy = 50.6 * 100 / 1000 = 5.06 nJ
        expected_active = 46.0 * 1.1 * 100.0 / 1000.0
        self.assertAlmostEqual(bg_active, expected_active, places=2)
        
        # Precharge: I_DD2N = 35 mA, V_DD = 1.1 V
        # Power = 35 * 1.1 = 38.5 mW
        # Energy = 38.5 * 200 / 1000 = 7.7 nJ
        expected_precharge = 35.0 * 1.1 * 200.0 / 1000.0
        self.assertAlmostEqual(bg_precharge, expected_precharge, places=2)


if __name__ == '__main__':
    unittest.main()

