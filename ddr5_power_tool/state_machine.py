"""
DRAM state machine and timing constraint tracking.
"""

from typing import Dict, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from ddr5_power_tool.workload_parser import CommandType
from ddr5_power_tool.spec_parser import MemorySpec


class BankState(Enum):
    """Bank state enumeration."""
    IDLE = "IDLE"  # Precharged
    ACTIVE = "ACTIVE"  # Row open
    ACTIVE_PDN = "ACTIVE_PDN"  # Active power-down
    PRE_PDN = "PRE_PDN"  # Precharged power-down
    REFRESHING = "REFRESHING"  # Currently refreshing


@dataclass
class BankStateInfo:
    """State information for a single bank."""
    state: BankState = BankState.IDLE
    open_row: Optional[int] = None
    last_activate_time: float = 0.0  # ns
    last_precharge_time: float = 0.0  # ns
    last_read_time: float = 0.0  # ns
    last_write_time: float = 0.0  # ns
    last_powerdown_time: float = 0.0  # ns


@dataclass
class TimingConstraints:
    """Timing constraint checker."""
    spec: MemorySpec
    
    def can_activate(self, bank_info: BankStateInfo, current_time: float) -> tuple[bool, Optional[str]]:
        """Check if ACTIVATE command can be issued."""
        if bank_info.state == BankState.ACTIVE:
            return False, "Bank already active"
        
        if bank_info.state == BankState.REFRESHING:
            return False, "Bank is refreshing"
        
        # Check tRC constraint (time since last activate)
        if bank_info.last_activate_time > 0:
            time_since_activate = current_time - bank_info.last_activate_time
            if time_since_activate < self.spec.timing.trc:
                return False, f"tRC violation: {time_since_activate:.2f} < {self.spec.timing.trc}"
        
        return True, None
    
    def can_read(self, bank_info: BankStateInfo, current_time: float) -> tuple[bool, Optional[str]]:
        """Check if READ command can be issued."""
        if bank_info.state != BankState.ACTIVE:
            return False, "Bank must be active for read"
        
        # Check tRCD constraint
        time_since_activate = current_time - bank_info.last_activate_time
        if time_since_activate < self.spec.timing.trcd:
            return False, f"tRCD violation: {time_since_activate:.2f} < {self.spec.timing.trcd}"
        
        return True, None
    
    def can_write(self, bank_info: BankStateInfo, current_time: float) -> tuple[bool, Optional[str]]:
        """Check if WRITE command can be issued."""
        if bank_info.state != BankState.ACTIVE:
            return False, "Bank must be active for write"
        
        # Check tRCD constraint
        time_since_activate = current_time - bank_info.last_activate_time
        if time_since_activate < self.spec.timing.trcd:
            return False, f"tRCD violation: {time_since_activate:.2f} < {self.spec.timing.trcd}"
        
        return True, None
    
    def can_precharge(self, bank_info: BankStateInfo, current_time: float) -> tuple[bool, Optional[str]]:
        """Check if PRECHARGE command can be issued."""
        if bank_info.state == BankState.IDLE:
            return False, "Bank already idle"
        
        if bank_info.state == BankState.REFRESHING:
            return False, "Bank is refreshing"
        
        # Check tRAS constraint (min time row must be active)
        # Only check if bank was activated (is in ACTIVE state)
        if bank_info.state == BankState.ACTIVE and bank_info.last_activate_time >= 0:
            time_since_activate = current_time - bank_info.last_activate_time
            if time_since_activate < self.spec.timing.tras:
                return False, f"tRAS violation: {time_since_activate:.2f} < {self.spec.timing.tras}"
        
        # Check tWR constraint (write recovery)
        if bank_info.last_write_time > 0:
            time_since_write = current_time - bank_info.last_write_time
            if time_since_write < self.spec.timing.twr:
                return False, f"tWR violation: {time_since_write:.2f} < {self.spec.timing.twr}"
        
        return True, None
    
    def can_refresh(self, current_time: float, last_refresh_time: float) -> tuple[bool, Optional[str]]:
        """Check if REFRESH command can be issued."""
        time_since_refresh = current_time - last_refresh_time
        if time_since_refresh < self.spec.timing.trfi:
            return False, f"tREFI violation: {time_since_refresh:.2f} < {self.spec.timing.trfi}"
        return True, None


class DRAMStateMachine:
    """DRAM state machine for tracking bank states."""
    
    def __init__(self, spec: MemorySpec):
        self.spec = spec
        self.banks: Dict[tuple[int, int], BankStateInfo] = {}  # (rank, bank) -> state
        self.constraints = TimingConstraints(spec)
        self.last_refresh_time: float = -1e9  # ns
        self.current_time: float = 0.0  # ns
        
        # Initialize all banks
        for rank in range(spec.architecture.nbr_of_ranks):
            for bank in range(spec.architecture.nbr_of_banks):
                self.banks[(rank, bank)] = BankStateInfo()
    
    def get_bank_info(self, rank: int, bank: int) -> BankStateInfo:
        """Get state info for a bank."""
        return self.banks[(rank, bank)]
    
    def update_time(self, time_ns: float):
        """Update current simulation time."""
        self.current_time = time_ns
    
    def execute_activate(self, rank: int, bank: int, row: int) -> tuple[bool, Optional[str]]:
        """Execute ACTIVATE command."""
        bank_info = self.get_bank_info(rank, bank)
        can_execute, error = self.constraints.can_activate(bank_info, self.current_time)
        
        if not can_execute:
            return False, error
        
        bank_info.state = BankState.ACTIVE
        bank_info.open_row = row
        bank_info.last_activate_time = self.current_time
        return True, None
    
    def execute_read(self, rank: int, bank: int) -> tuple[bool, Optional[str]]:
        """Execute READ command."""
        bank_info = self.get_bank_info(rank, bank)
        can_execute, error = self.constraints.can_read(bank_info, self.current_time)
        
        if not can_execute:
            return False, error
        
        bank_info.last_read_time = self.current_time
        return True, None
    
    def execute_write(self, rank: int, bank: int) -> tuple[bool, Optional[str]]:
        """Execute WRITE command."""
        bank_info = self.get_bank_info(rank, bank)
        can_execute, error = self.constraints.can_write(bank_info, self.current_time)
        
        if not can_execute:
            return False, error
        
        bank_info.last_write_time = self.current_time
        return True, None
    
    def execute_precharge(self, rank: int, bank: int) -> tuple[bool, Optional[str]]:
        """Execute PRECHARGE command."""
        bank_info = self.get_bank_info(rank, bank)
        can_execute, error = self.constraints.can_precharge(bank_info, self.current_time)
        
        if not can_execute:
            return False, error
        
        bank_info.state = BankState.IDLE
        bank_info.open_row = None
        bank_info.last_precharge_time = self.current_time
        return True, None
    
    def execute_refresh(self) -> tuple[bool, Optional[str]]:
        """Execute REFRESH command."""
        can_execute, error = self.constraints.can_refresh(self.current_time, self.last_refresh_time)
        
        if not can_execute:
            return False, error
        
        # Mark all banks as refreshing
        for bank_info in self.banks.values():
            if bank_info.state == BankState.ACTIVE:
                bank_info.state = BankState.REFRESHING
        
        self.last_refresh_time = self.current_time
        
        # Refresh completes after tRFC
        refresh_end_time = self.current_time + self.spec.timing.trfc
        
        # After refresh, banks return to their previous state (or IDLE)
        for bank_info in self.banks.values():
            if bank_info.state == BankState.REFRESHING:
                bank_info.state = BankState.IDLE
                bank_info.open_row = None
        
        return True, None
    
    def get_active_banks(self) -> List[tuple[int, int]]:
        """Get list of currently active banks."""
        active = []
        for (rank, bank), info in self.banks.items():
            if info.state == BankState.ACTIVE:
                active.append((rank, bank))
        return active
    
    def get_idle_banks(self) -> List[tuple[int, int]]:
        """Get list of currently idle banks."""
        idle = []
        for (rank, bank), info in self.banks.items():
            if info.state == BankState.IDLE:
                idle.append((rank, bank))
        return idle

