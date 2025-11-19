"""Tests for workload parser."""

import unittest
import json
import tempfile
import os
from ddr5_power_tool.workload_parser import Workload, Command, CommandType, WorkloadMetadata


class TestWorkloadParser(unittest.TestCase):
    """Test workload parser."""
    
    def test_command_creation(self):
        """Test creating command from dict."""
        cmd_dict = {
            "timestamp": 0,
            "command": "ACT",
            "bank": 0,
            "rank": 0,
            "row": 512
        }
        
        cmd = Command.from_dict(cmd_dict)
        
        self.assertEqual(cmd.timestamp, 0)
        self.assertEqual(cmd.command, CommandType.ACT)
        self.assertEqual(cmd.bank, 0)
        self.assertEqual(cmd.row, 512)
    
    def test_load_workload_from_json(self):
        """Test loading workload from JSON."""
        workload_data = {
            "commands": [
                {
                    "timestamp": 0,
                    "command": "ACT",
                    "bank": 0,
                    "rank": 0,
                    "row": 512
                },
                {
                    "timestamp": 50,
                    "command": "RD",
                    "bank": 0,
                    "rank": 0,
                    "burstLength": 16
                },
                {
                    "timestamp": 5000,
                    "command": "END_OF_SIMULATION"
                }
            ],
            "metadata": {
                "dataRate": 6400,
                "temperature": 50
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(workload_data, f)
            temp_path = f.name
        
        try:
            workload = Workload.from_json(temp_path)
            
            self.assertEqual(len(workload.commands), 3)
            self.assertEqual(workload.commands[0].command, CommandType.ACT)
            self.assertEqual(workload.metadata.data_rate, 6400)
        finally:
            os.unlink(temp_path)
    
    def test_invalid_command(self):
        """Test handling invalid command type."""
        cmd_dict = {
            "timestamp": 0,
            "command": "INVALID",
            "bank": 0
        }
        
        with self.assertRaises(ValueError):
            Command.from_dict(cmd_dict)


if __name__ == '__main__':
    unittest.main()

