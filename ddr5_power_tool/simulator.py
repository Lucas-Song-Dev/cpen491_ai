"""
Main simulation engine for DDR5/LPDDR5 power estimation.
"""

from typing import Optional, List, Dict
from ddr5_power_tool.spec_parser import MemorySpec
from ddr5_power_tool.workload_parser import Workload, Command, CommandType
from ddr5_power_tool.state_machine import DRAMStateMachine
from ddr5_power_tool.power_calculator import PowerCalculator, PowerResult


class Simulator:
    """Main simulation engine."""
    
    def __init__(self, spec: MemorySpec):
        self.spec = spec
        self.state_machine = DRAMStateMachine(spec)
        self.power_calculator = PowerCalculator(spec, self.state_machine)
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def simulate(self, workload: Workload) -> PowerResult:
        """
        Run power simulation on workload.
        """
        self.errors.clear()
        self.warnings.clear()
        
        commands = workload.commands
        if not commands:
            self.errors.append("No commands in workload")
            return self.power_calculator.result
        
        # Sort commands by timestamp
        sorted_commands = sorted(commands, key=lambda c: c.timestamp)
        
        # Convert timestamps from clock cycles to nanoseconds
        tck_ns = self.spec.timing.tck
        
        last_time_ns = 0.0
        
        for i, cmd in enumerate(sorted_commands):
            if cmd.command == CommandType.END_OF_SIMULATION:
                # Finalize background power accumulation
                current_time_ns = cmd.timestamp * tck_ns
                self.power_calculator.accumulate_background_power(last_time_ns, current_time_ns)
                last_time_ns = current_time_ns
                break
            
            current_time_ns = cmd.timestamp * tck_ns
            next_time_ns = sorted_commands[i + 1].timestamp * tck_ns if i + 1 < len(sorted_commands) else current_time_ns + tck_ns
            
            # Accumulate background power since last command
            if current_time_ns > last_time_ns:
                self.power_calculator.accumulate_background_power(last_time_ns, current_time_ns)
            
            # Update state machine time
            self.state_machine.update_time(current_time_ns)
            
            # Execute command in state machine
            rank = cmd.rank if cmd.rank is not None else 0
            bank = cmd.bank if cmd.bank is not None else 0
            
            success, error = self._execute_command(cmd, rank, bank)
            
            if not success:
                self.errors.append(f"Command {cmd.command.value} at {cmd.timestamp} cycles: {error}")
                last_time_ns = current_time_ns
                continue
            
            # Calculate power for this command
            energy = self.power_calculator.process_command(
                cmd.command,
                rank,
                bank,
                current_time_ns,
                next_time_ns,
                cmd.row,
                cmd.column,
                cmd.burst_length
            )
            
            self.power_calculator.result.core_energy += energy
            
            last_time_ns = current_time_ns
        
        # Finalize calculations
        final_time_ns = last_time_ns if last_time_ns > 0 else sorted_commands[-1].timestamp * tck_ns
        self.power_calculator.finalize(final_time_ns)
        
        return self.power_calculator.result
    
    def _execute_command(self, cmd: Command, rank: int, bank: int) -> tuple[bool, Optional[str]]:
        """Execute command in state machine."""
        if cmd.command == CommandType.ACT:
            if cmd.row is None:
                return False, "ACT command requires row"
            return self.state_machine.execute_activate(rank, bank, cmd.row)
        
        elif cmd.command == CommandType.RD:
            return self.state_machine.execute_read(rank, bank)
        
        elif cmd.command == CommandType.WR:
            return self.state_machine.execute_write(rank, bank)
        
        elif cmd.command == CommandType.PRE:
            return self.state_machine.execute_precharge(rank, bank)
        
        elif cmd.command == CommandType.PREA:
            # Precharge all banks
            success = True
            error_msg = None
            for b in range(self.spec.architecture.nbr_of_banks):
                s, e = self.state_machine.execute_precharge(rank, b)
                if not s:
                    success = False
                    error_msg = e
            return success, error_msg
        
        elif cmd.command == CommandType.REF:
            return self.state_machine.execute_refresh()
        
        elif cmd.command == CommandType.REFPB:
            # Per-bank refresh (LPDDR5)
            if cmd.bank is None:
                return False, "REFPB command requires bank"
            # For now, treat as regular refresh (simplified)
            return self.state_machine.execute_refresh()
        
        else:
            return True, None  # Other commands don't need state machine updates
    
    def get_errors(self) -> List[str]:
        """Get list of errors encountered during simulation."""
        return self.errors
    
    def get_warnings(self) -> List[str]:
        """Get list of warnings encountered during simulation."""
        return self.warnings

