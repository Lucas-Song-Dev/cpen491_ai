"""Tests for specification parser."""

import unittest
import json
import tempfile
import os
from ddr5_power_tool.spec_parser import MemorySpec, MemoryPowerSpec, MemoryTimingSpec, ArchitectureSpec


class TestSpecParser(unittest.TestCase):
    """Test specification parser."""
    
    def test_power_spec_creation(self):
        """Test creating power spec from data."""
        power = MemoryPowerSpec(
            idd0=51.0,
            idd2n=35.0,
            idd2p=25.0,
            idd3n=46.0,
            idd3p=15.0,
            idd4r=146.0,
            idd4w=120.0,
            idd5b=80.0,
            idd6=3.0,
            vdd=1.1,
            vddq=1.1,
            vddca=1.1
        )
        
        self.assertEqual(power.idd0, 51.0)
        self.assertEqual(power.vdd, 1.1)
    
    def test_timing_spec_trc_calculation(self):
        """Test that tRC is calculated if not provided."""
        timing = MemoryTimingSpec(
            tck=0.312,
            tras=32.0,
            trp=13.75,
            trcd=13.75,
            trfc=280.0
        )
        
        self.assertEqual(timing.trc, 45.75)  # tras + trp
    
    def test_load_from_json(self):
        """Test loading spec from JSON file."""
        spec_data = {
            "mempowerspec": {
                "idd0": 51.0,
                "idd2n": 35.0,
                "idd2p": 25.0,
                "idd3n": 46.0,
                "idd3p": 15.0,
                "idd4r": 146.0,
                "idd4w": 120.0,
                "idd5b": 80.0,
                "idd6": 3.0,
                "vdd": 1.1,
                "vddq": 1.1,
                "vddca": 1.1
            },
            "memtimingspec": {
                "tck": 0.312,
                "tras": 32.0,
                "trp": 13.75,
                "trcd": 13.75,
                "trfc": 280.0
            },
            "architecture": {
                "nbrOfRanks": 1,
                "nbrOfBanks": 16,
                "nbrOfColumns": 1024,
                "nbrOfRows": 65536,
                "width": 64,
                "burstLength": 16,
                "density": 16
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(spec_data, f)
            temp_path = f.name
        
        try:
            spec = MemorySpec.from_json(temp_path)
            
            self.assertEqual(spec.power.idd0, 51.0)
            self.assertEqual(spec.timing.tck, 0.312)
            self.assertEqual(spec.architecture.nbr_of_banks, 16)
        finally:
            os.unlink(temp_path)


if __name__ == '__main__':
    unittest.main()

