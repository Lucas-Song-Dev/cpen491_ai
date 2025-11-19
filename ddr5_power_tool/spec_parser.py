"""
JSON specification parser for memory power and timing specifications.
"""

import json
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class MemoryPowerSpec:
    """Memory power specification from datasheet."""
    idd0: float  # mA, average activate cycle current
    idd2n: float  # mA, idle precharged
    idd2p: float  # mA, precharged power-down
    idd3n: float  # mA, idle active
    idd3p: float  # mA, active power-down
    idd4r: float  # mA, read current
    idd4w: float  # mA, write current
    idd5b: float  # mA, auto-refresh current
    idd6: float  # mA, self-refresh
    vdd: float  # V, core voltage
    vddq: float  # V, I/O voltage
    vddca: float  # V, command/address voltage
    ipp: float = 0.5  # mA (if applicable)
    temperature: float = 50  # degrees C


@dataclass
class MemoryTimingSpec:
    """Memory timing specification from JEDEC."""
    tck: float  # ns, clock cycle
    tras: float  # ns, row active time
    trp: float  # ns, precharge time
    trcd: float  # ns, row to column delay
    trfc: float  # ns, refresh cycle time
    trfcpb: Optional[float] = None  # ns, per-bank refresh (LPDDR5)
    trfi: float = 7800.0  # ns, refresh interval
    twr: float = 15.0  # ns, write recovery
    twtr: float = 7.5  # ns, write to read
    trrd: float = 4.7  # ns, row to row delay
    tfaw: float = 13.75  # ns, four-activate window
    trc: Optional[float] = None  # ns, row cycle time (calculated if not provided)
    txp: float = 5.0  # ns, exit power-down
    txsdr: float = 70.0  # ns, exit self-refresh
    txsdll: float = 512.0  # tCK, DLL lock time

    def __post_init__(self):
        """Calculate tRC if not provided."""
        if self.trc is None:
            self.trc = self.tras + self.trp


@dataclass
class ArchitectureSpec:
    """Memory architecture specification."""
    nbr_of_ranks: int
    nbr_of_banks: int
    nbr_of_columns: int
    nbr_of_rows: int
    width: int  # bit width (DIMM)
    burst_length: int  # BL16 for DDR5, BL32 for LPDDR5
    density: int  # Gb per die
    refresh_mode: str = "all-bank"  # "all-bank" or "per-bank"


@dataclass
class MemorySpec:
    """Complete memory specification."""
    power: MemoryPowerSpec
    timing: MemoryTimingSpec
    architecture: ArchitectureSpec

    @classmethod
    def from_json(cls, json_path: str) -> "MemorySpec":
        """Load specification from JSON file."""
        with open(json_path, 'r') as f:
            data = json.load(f)
        
        mempowerspec = data.get("mempowerspec", {})
        memtimingspec = data.get("memtimingspec", {})
        architecture = data.get("architecture", {})
        
        # Convert camelCase to snake_case for architecture
        arch_dict = {
            "nbr_of_ranks": architecture.get("nbrOfRanks", 1),
            "nbr_of_banks": architecture.get("nbrOfBanks", 16),
            "nbr_of_columns": architecture.get("nbrOfColumns", 1024),
            "nbr_of_rows": architecture.get("nbrOfRows", 65536),
            "width": architecture.get("width", 64),
            "burst_length": architecture.get("burstLength", 16),
            "density": architecture.get("density", 16),
            "refresh_mode": architecture.get("refreshMode", "all-bank")
        }
        
        power_spec = MemoryPowerSpec(**mempowerspec)
        timing_spec = MemoryTimingSpec(**memtimingspec)
        arch_spec = ArchitectureSpec(**arch_dict)
        
        return cls(power=power_spec, timing=timing_spec, architecture=arch_spec)

