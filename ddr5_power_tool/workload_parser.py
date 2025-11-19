"""
Workload parser for command traces.
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class CommandType(Enum):
    """DRAM command types."""
    ACT = "ACT"  # Activate
    RD = "RD"  # Read
    WR = "WR"  # Write
    PRE = "PRE"  # Precharge
    PREA = "PREA"  # Precharge all
    REF = "REF"  # Refresh
    REFPB = "REFPB"  # Per-bank refresh (LPDDR5)
    PDN = "PDN"  # Power-down entry
    SR = "SR"  # Self-refresh entry
    END_OF_SIMULATION = "END_OF_SIMULATION"


@dataclass
class Command:
    """Single DRAM command."""
    timestamp: int  # clock cycles
    command: CommandType
    bank: Optional[int] = None
    rank: Optional[int] = None
    row: Optional[int] = None
    column: Optional[int] = None
    burst_length: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Command":
        """Create command from dictionary."""
        cmd_str = data.get("command", "").upper()
        try:
            cmd_type = CommandType[cmd_str]
        except KeyError:
            raise ValueError(f"Unknown command type: {cmd_str}")
        
        return cls(
            timestamp=data["timestamp"],
            command=cmd_type,
            bank=data.get("bank"),
            rank=data.get("rank", 0),
            row=data.get("row"),
            column=data.get("column"),
            burst_length=data.get("burstLength")
        )


@dataclass
class WorkloadMetadata:
    """Workload metadata."""
    data_rate: int = 6400  # MT/s
    temperature: float = 50  # degrees C
    toggle_rates: Optional[Dict[str, float]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkloadMetadata":
        """Create metadata from dictionary."""
        toggle_rates = data.get("toggleRates", {})
        return cls(
            data_rate=data.get("dataRate", 6400),
            temperature=data.get("temperature", 50),
            toggle_rates=toggle_rates
        )


@dataclass
class Workload:
    """Complete workload specification."""
    commands: List[Command]
    metadata: WorkloadMetadata

    @classmethod
    def from_json(cls, json_path: str) -> "Workload":
        """Load workload from JSON file."""
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        commands = [Command.from_dict(cmd) for cmd in data.get("commands", [])]
        metadata_dict = data.get("metadata", {})
        if metadata_dict:
            metadata = WorkloadMetadata.from_dict(metadata_dict)
        else:
            metadata = WorkloadMetadata()
        
        return cls(commands=commands, metadata=metadata)

