"""
Power calculation engine for DDR5/LPDDR5.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from ddr5_power_tool.spec_parser import MemorySpec
from ddr5_power_tool.state_machine import DRAMStateMachine, BankState
from ddr5_power_tool.workload_parser import CommandType


@dataclass
class PowerResult:
    """Power calculation result."""
    core_energy: float = 0.0  # nJ
    interface_energy: float = 0.0  # nJ
    total_energy: float = 0.0  # nJ
    average_power: float = 0.0  # mW
    simulation_time: float = 0.0  # ns
    
    # Breakdown by component
    activation_energy: float = 0.0
    read_energy: float = 0.0
    write_energy: float = 0.0
    precharge_energy: float = 0.0
    refresh_energy: float = 0.0
    background_active_energy: float = 0.0
    background_precharge_energy: float = 0.0
    powerdown_energy: float = 0.0
    termination_energy: float = 0.0
    dynamic_io_energy: float = 0.0


class PowerCalculator:
    """Power calculation engine."""
    
    def __init__(self, spec: MemorySpec, state_machine: DRAMStateMachine):
        self.spec = spec
        self.state_machine = state_machine
        self.result = PowerResult()
        
        # State tracking for background power
        self.state_history: List[Dict] = []  # List of (time, state) tuples
        self.last_state_time: float = 0.0
        
        # Refresh tracking
        self.refresh_count: int = 0
        self.last_refresh_time: float = -1e9
        
        # I/O power parameters
        self.odt_resistance: float = 120.0  # Ohms (typical)
        self.dq_capacitance: float = 2.0  # pF (typical)
        self.switching_activity: float = 0.5  # 50% switching
    
    def calculate_activation_power(self, duration_ns: float) -> float:
        """
        Calculate activation power.
        P_ACT = (I_DD0 - I_DD3N) * V_DD
        """
        idd0 = self.spec.power.idd0  # mA
        idd3n = self.spec.power.idd3n  # mA
        
        # Account for timing: activation happens over tRAS portion of tRC
        tras = self.spec.timing.tras
        trc = self.spec.timing.trc
        
        # Average current during activation cycle
        # I_ACT = I_DD0 * (tRAS/tRC) + I_DD3N * ((tRC-tRAS)/tRC) - I_DD3N
        # Simplified: extra current during activation
        idd_activation = idd0 - idd3n
        
        power_mw = idd_activation * self.spec.power.vdd  # mW
        energy_nj = power_mw * duration_ns / 1000.0  # nJ (mW * ns / 1000 = nJ)
        
        return energy_nj
    
    def calculate_read_power(self, duration_ns: float, burst_length: Optional[int] = None) -> float:
        """
        Calculate read power.
        P_RD = (I_DD4R - I_DD3N) * V_DD
        """
        idd4r = self.spec.power.idd4r  # mA
        idd3n = self.spec.power.idd3n  # mA
        
        idd_read = idd4r - idd3n
        power_mw = idd_read * self.spec.power.vdd  # mW
        energy_nj = power_mw * duration_ns / 1000.0  # nJ
        
        # Add I/O power for read
        if burst_length:
            io_energy = self.calculate_io_power_read(burst_length, duration_ns)
            energy_nj += io_energy
        
        return energy_nj
    
    def calculate_write_power(self, duration_ns: float, burst_length: Optional[int] = None) -> float:
        """
        Calculate write power.
        P_WR = (I_DD4W - I_DD3N) * V_DD
        """
        idd4w = self.spec.power.idd4w  # mA
        idd3n = self.spec.power.idd3n  # mA
        
        idd_write = idd4w - idd3n
        power_mw = idd_write * self.spec.power.vdd  # mW
        energy_nj = power_mw * duration_ns / 1000.0  # nJ
        
        # Add I/O power for write
        if burst_length:
            io_energy = self.calculate_io_power_write(burst_length, duration_ns)
            energy_nj += io_energy
        
        return energy_nj
    
    def calculate_precharge_power(self, duration_ns: float) -> float:
        """
        Calculate precharge power.
        Similar to activation, accounts for precharge cycle.
        """
        idd0 = self.spec.power.idd0  # mA
        idd3n = self.spec.power.idd3n  # mA
        
        idd_precharge = idd0 - idd3n
        power_mw = idd_precharge * self.spec.power.vdd  # mW
        energy_nj = power_mw * duration_ns / 1000.0  # nJ
        
        return energy_nj
    
    def calculate_refresh_power(self, duration_ns: float) -> float:
        """
        Calculate refresh power.
        P_REF = I_DD5B * V_DD
        """
        idd5b = self.spec.power.idd5b  # mA
        power_mw = idd5b * self.spec.power.vdd  # mW
        energy_nj = power_mw * duration_ns / 1000.0  # nJ
        
        return energy_nj
    
    def calculate_background_power(self, active_stby_time_ns: float, active_pdn_time_ns: float,
                                   precharge_stby_time_ns: float, precharge_pdn_time_ns: float) -> tuple[float, float]:
        """
        Calculate background power for active and precharge states.
        Separates standby (CKE high) from power-down (CKE low) states.
        
        Based on Table 2 formulas:
        - Pds(PRE_STBY) = IDD2N × VDD
        - Pds(PRE_PDN) = IDD2P × VDD
        - Pds(ACT_STBY) = IDD3N × VDD
        - Pds(ACT_PDN) = IDD3P × VDD
        
        Returns (active_energy, precharge_energy) in nJ
        """
        # Active standby power (ACT_STBY)
        idd3n = self.spec.power.idd3n  # mA
        power_active_stby_mw = idd3n * self.spec.power.vdd  # mW
        energy_active_stby_nj = power_active_stby_mw * active_stby_time_ns / 1000.0  # nJ
        
        # Active power-down power (ACT_PDN)
        idd3p = self.spec.power.idd3p  # mA
        power_active_pdn_mw = idd3p * self.spec.power.vdd  # mW
        energy_active_pdn_nj = power_active_pdn_mw * active_pdn_time_ns / 1000.0  # nJ
        
        # Precharge standby power (PRE_STBY)
        idd2n = self.spec.power.idd2n  # mA
        power_precharge_stby_mw = idd2n * self.spec.power.vdd  # mW
        energy_precharge_stby_nj = power_precharge_stby_mw * precharge_stby_time_ns / 1000.0  # nJ
        
        # Precharge power-down power (PRE_PDN)
        idd2p = self.spec.power.idd2p  # mA
        power_precharge_pdn_mw = idd2p * self.spec.power.vdd  # mW
        energy_precharge_pdn_nj = power_precharge_pdn_mw * precharge_pdn_time_ns / 1000.0  # nJ
        
        # Total active energy (standby + power-down)
        active_energy_nj = energy_active_stby_nj + energy_active_pdn_nj
        
        # Total precharge energy (standby + power-down)
        precharge_energy_nj = energy_precharge_stby_nj + energy_precharge_pdn_nj
        
        return active_energy_nj, precharge_energy_nj
    
    def calculate_powerdown_power(self, duration_ns: float, is_active_pdn: bool) -> float:
        """
        Calculate power-down power.
        P_APD = I_DD3P * V_DD (active power-down)
        P_PPD = I_DD2P * V_DD (precharge power-down)
        """
        if is_active_pdn:
            idd = self.spec.power.idd3p  # mA
        else:
            idd = self.spec.power.idd2p  # mA
        
        power_mw = idd * self.spec.power.vdd  # mW
        energy_nj = power_mw * duration_ns / 1000.0  # nJ
        
        return energy_nj
    
    def calculate_termination_power(self, duration_ns: float, is_read: bool = True) -> float:
        """
        Calculate ODT termination power.
        P_term = V_term^2 / R_term * (fraction of time active)
        """
        # For DDR5: termination to VDDQ/2
        # For LPDDR5: termination to GND (lower power)
        vddq = self.spec.power.vddq
        
        # Assume DDR5-style termination (can be adjusted for LPDDR5)
        v_term = vddq / 2.0  # V
        r_term = self.odt_resistance  # Ohms
        
        # Power in mW
        power_mw = (v_term ** 2 / r_term) * 1000.0  # mW
        
        # Only active during read/write operations
        # Assume 50% duty cycle during data transfer
        duty_cycle = 0.5 if is_read else 0.5
        energy_nj = power_mw * duration_ns * duty_cycle / 1000.0  # nJ
        
        return energy_nj
    
    def calculate_io_power_read(self, burst_length: int, duration_ns: float) -> float:
        """
        Calculate dynamic I/O power for read operations.
        P_DQ = C_DQ * V_swing * f * switching_activity
        """
        vddq = self.spec.power.vddq
        v_swing = vddq  # Full swing
        c_dq = self.dq_capacitance  # pF
        n_dq_pins = self.spec.architecture.width  # number of data pins
        
        # Frequency in GHz
        tck_ns = self.spec.timing.tck
        freq_ghz = 1.0 / (tck_ns * 2.0)  # DDR: 2 transfers per cycle
        
        # Energy per transition: E = 0.5 * C * V^2
        energy_per_transition_pj = 0.5 * c_dq * (v_swing ** 2)  # pJ
        
        # Total transitions: burst_length * n_dq_pins * switching_activity
        n_transitions = burst_length * n_dq_pins * self.switching_activity
        
        # Total energy in nJ
        energy_nj = energy_per_transition_pj * n_transitions / 1000.0  # nJ
        
        return energy_nj
    
    def calculate_io_power_write(self, burst_length: int, duration_ns: float) -> float:
        """
        Calculate dynamic I/O power for write operations.
        Similar to read, but may have different switching characteristics.
        """
        return self.calculate_io_power_read(burst_length, duration_ns)
    
    def process_command(self, cmd_type: CommandType, rank: int, bank: int, 
                       current_time_ns: float, next_time_ns: Optional[float] = None,
                       row: Optional[int] = None, column: Optional[int] = None,
                       burst_length: Optional[int] = None) -> float:
        """
        Process a single command and return energy consumed.
        """
        duration_ns = (next_time_ns - current_time_ns) if next_time_ns else self.spec.timing.tck
        
        energy_nj = 0.0
        
        if cmd_type == CommandType.ACT:
            # Activation energy
            act_energy = self.calculate_activation_power(self.spec.timing.tras)
            energy_nj += act_energy
            self.result.activation_energy += act_energy
            
        elif cmd_type == CommandType.RD:
            # Read energy
            bl = burst_length or self.spec.architecture.burst_length
            rd_energy = self.calculate_read_power(duration_ns, bl)
            energy_nj += rd_energy
            self.result.read_energy += rd_energy
            
            # Termination power
            term_energy = self.calculate_termination_power(duration_ns, is_read=True)
            energy_nj += term_energy
            self.result.termination_energy += term_energy
            
        elif cmd_type == CommandType.WR:
            # Write energy
            bl = burst_length or self.spec.architecture.burst_length
            wr_energy = self.calculate_write_power(duration_ns, bl)
            energy_nj += wr_energy
            self.result.write_energy += wr_energy
            
            # Termination power
            term_energy = self.calculate_termination_power(duration_ns, is_read=False)
            energy_nj += term_energy
            self.result.termination_energy += term_energy
            
        elif cmd_type == CommandType.PRE or cmd_type == CommandType.PREA:
            # Precharge energy
            pre_energy = self.calculate_precharge_power(self.spec.timing.trp)
            energy_nj += pre_energy
            self.result.precharge_energy += pre_energy
            
        elif cmd_type == CommandType.REF or cmd_type == CommandType.REFPB:
            # Refresh energy
            trfc = self.spec.timing.trfcpb if (cmd_type == CommandType.REFPB and self.spec.timing.trfcpb) else self.spec.timing.trfc
            ref_energy = self.calculate_refresh_power(trfc)
            energy_nj += ref_energy
            self.result.refresh_energy += ref_energy
            self.refresh_count += 1
            self.last_refresh_time = current_time_ns
        
        return energy_nj
    
    def accumulate_background_power(self, start_time_ns: float, end_time_ns: float):
        """
        Accumulate background power between commands.
        Properly separates standby (CKE high) from power-down (CKE low) states.
        """
        duration_ns = end_time_ns - start_time_ns
        if duration_ns <= 0:
            return
        
        from ddr5_power_tool.state_machine import BankState
        
        # Count banks in each state
        n_active_stby = 0  # ACTIVE (standby, CKE high)
        n_active_pdn = 0   # ACTIVE_PDN (power-down, CKE low)
        n_precharge_stby = 0  # IDLE (standby, CKE high)
        n_precharge_pdn = 0   # PRE_PDN (power-down, CKE low)
        
        n_total = self.spec.architecture.nbr_of_ranks * self.spec.architecture.nbr_of_banks
        
        for (rank, bank), bank_info in self.state_machine.banks.items():
            if bank_info.state == BankState.ACTIVE:
                n_active_stby += 1
            elif bank_info.state == BankState.ACTIVE_PDN:
                n_active_pdn += 1
            elif bank_info.state == BankState.IDLE:
                n_precharge_stby += 1
            elif bank_info.state == BankState.PRE_PDN:
                n_precharge_pdn += 1
        
        # Calculate time-weighted background power
        # Assume uniform distribution across banks
        if n_total > 0:
            active_stby_time = duration_ns * (n_active_stby / n_total)
            active_pdn_time = duration_ns * (n_active_pdn / n_total)
            precharge_stby_time = duration_ns * (n_precharge_stby / n_total)
            precharge_pdn_time = duration_ns * (n_precharge_pdn / n_total)
        else:
            active_stby_time = 0.0
            active_pdn_time = 0.0
            precharge_stby_time = duration_ns
            precharge_pdn_time = 0.0
        
        bg_active, bg_precharge = self.calculate_background_power(
            active_stby_time, active_pdn_time,
            precharge_stby_time, precharge_pdn_time
        )
        
        self.result.background_active_energy += bg_active
        self.result.background_precharge_energy += bg_precharge
    
    def finalize(self, simulation_time_ns: float):
        """
        Finalize power calculations and compute totals.
        """
        self.result.simulation_time = simulation_time_ns
        
        # Sum core energy
        self.result.core_energy = (
            self.result.activation_energy +
            self.result.read_energy +
            self.result.write_energy +
            self.result.precharge_energy +
            self.result.refresh_energy +
            self.result.background_active_energy +
            self.result.background_precharge_energy +
            self.result.powerdown_energy
        )
        
        # Sum interface energy
        self.result.interface_energy = (
            self.result.termination_energy +
            self.result.dynamic_io_energy
        )
        
        # Total energy
        self.result.total_energy = self.result.core_energy + self.result.interface_energy
        
        # Average power in mW
        if simulation_time_ns > 0:
            self.result.average_power = (self.result.total_energy / simulation_time_ns) * 1000.0  # mW
        else:
            self.result.average_power = 0.0

