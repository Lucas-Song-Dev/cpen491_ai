"""Tests for state machine."""

import unittest
from ddr5_power_tool.spec_parser import MemorySpec, MemoryPowerSpec, MemoryTimingSpec, ArchitectureSpec
from ddr5_power_tool.state_machine import DRAMStateMachine, BankState


class TestStateMachine(unittest.TestCase):
    """Test DRAM state machine."""
    
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
    
    def test_initial_state(self):
        """Test initial bank states."""
        bank_info = self.state_machine.get_bank_info(0, 0)
        self.assertEqual(bank_info.state, BankState.IDLE)
        self.assertIsNone(bank_info.open_row)
    
    def test_activate(self):
        """Test ACTIVATE command."""
        self.state_machine.update_time(0.0)
        success, error = self.state_machine.execute_activate(0, 0, 512)
        
        self.assertTrue(success)
        bank_info = self.state_machine.get_bank_info(0, 0)
        self.assertEqual(bank_info.state, BankState.ACTIVE)
        self.assertEqual(bank_info.open_row, 512)
    
    def test_read_requires_active(self):
        """Test that READ requires active bank."""
        self.state_machine.update_time(0.0)
        success, error = self.state_machine.execute_read(0, 0)
        
        self.assertFalse(success)
        self.assertIn("active", error.lower())
    
    def test_read_after_activate(self):
        """Test READ after ACTIVATE with tRCD constraint."""
        self.state_machine.update_time(0.0)
        self.state_machine.execute_activate(0, 0, 512)
        
        # Try read too early (before tRCD)
        self.state_machine.update_time(5.0)  # Less than tRCD (13.75 ns)
        success, error = self.state_machine.execute_read(0, 0)
        self.assertFalse(success)
        self.assertIn("trcd", error.lower())
        
        # Try read after tRCD
        self.state_machine.update_time(15.0)  # After tRCD
        success, error = self.state_machine.execute_read(0, 0)
        self.assertTrue(success)
    
    def test_precharge_requires_tras(self):
        """Test that PRECHARGE requires tRAS."""
        self.state_machine.update_time(0.0)
        self.state_machine.execute_activate(0, 0, 512)
        
        # Try precharge too early (before tRAS)
        self.state_machine.update_time(20.0)  # Less than tRAS (32 ns)
        success, error = self.state_machine.execute_precharge(0, 0)
        self.assertFalse(success)
        self.assertIn("tras", error.lower())
        
        # Try precharge after tRAS
        self.state_machine.update_time(35.0)  # After tRAS
        success, error = self.state_machine.execute_precharge(0, 0)
        self.assertTrue(success)
        bank_info = self.state_machine.get_bank_info(0, 0)
        self.assertEqual(bank_info.state, BankState.IDLE)


if __name__ == '__main__':
    unittest.main()

