"""
Command-line interface for DDR5/LPDDR5 power tool.
"""

import argparse
import json
import sys
from pathlib import Path
from ddr5_power_tool.spec_parser import MemorySpec
from ddr5_power_tool.workload_parser import Workload
from ddr5_power_tool.simulator import Simulator


def format_energy(energy_nj: float) -> str:
    """Format energy value."""
    if energy_nj >= 1e6:
        return f"{energy_nj / 1e6:.3f} mJ"
    elif energy_nj >= 1e3:
        return f"{energy_nj / 1e3:.3f} µJ"
    else:
        return f"{energy_nj:.3f} nJ"


def format_power(power_mw: float) -> str:
    """Format power value."""
    if power_mw >= 1000:
        return f"{power_mw / 1000:.3f} W"
    else:
        return f"{power_mw:.3f} mW"


def print_results(result, simulator: Simulator):
    """Print simulation results."""
    print("\n" + "="*60)
    print("DDR5/LPDDR5 Power Simulation Results")
    print("="*60)
    
    print(f"\nSimulation Time: {result.simulation_time / 1e6:.3f} µs")
    print(f"Average Power: {format_power(result.average_power)}")
    print(f"Total Energy: {format_energy(result.total_energy)}")
    
    print("\n" + "-"*60)
    print("Energy Breakdown (Core):")
    print("-"*60)
    print(f"  Activation:     {format_energy(result.activation_energy)}")
    print(f"  Read:           {format_energy(result.read_energy)}")
    print(f"  Write:          {format_energy(result.write_energy)}")
    print(f"  Precharge:      {format_energy(result.precharge_energy)}")
    print(f"  Refresh:        {format_energy(result.refresh_energy)}")
    print(f"  BG (Active):    {format_energy(result.background_active_energy)}")
    print(f"  BG (Precharge): {format_energy(result.background_precharge_energy)}")
    print(f"  Power-Down:     {format_energy(result.powerdown_energy)}")
    print(f"  Core Total:     {format_energy(result.core_energy)}")
    
    print("\n" + "-"*60)
    print("Energy Breakdown (Interface):")
    print("-"*60)
    print(f"  Termination:    {format_energy(result.termination_energy)}")
    print(f"  Dynamic I/O:    {format_energy(result.dynamic_io_energy)}")
    print(f"  Interface Total: {format_energy(result.interface_energy)}")
    
    errors = simulator.get_errors()
    warnings = simulator.get_warnings()
    
    if errors:
        print("\n" + "="*60)
        print("ERRORS:")
        print("="*60)
        for error in errors:
            print(f"  ❌ {error}")
    
    if warnings:
        print("\n" + "="*60)
        print("WARNINGS:")
        print("="*60)
        for warning in warnings:
            print(f"  ⚠️  {warning}")


def export_json(result, output_path: str):
    """Export results to JSON."""
    data = {
        "simulation_time_ns": result.simulation_time,
        "average_power_mw": result.average_power,
        "total_energy_nj": result.total_energy,
        "core_energy_nj": result.core_energy,
        "interface_energy_nj": result.interface_energy,
        "breakdown": {
            "activation_energy_nj": result.activation_energy,
            "read_energy_nj": result.read_energy,
            "write_energy_nj": result.write_energy,
            "precharge_energy_nj": result.precharge_energy,
            "refresh_energy_nj": result.refresh_energy,
            "background_active_energy_nj": result.background_active_energy,
            "background_precharge_energy_nj": result.background_precharge_energy,
            "powerdown_energy_nj": result.powerdown_energy,
            "termination_energy_nj": result.termination_energy,
            "dynamic_io_energy_nj": result.dynamic_io_energy,
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nResults exported to: {output_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="DDR5/LPDDR5 Power Measurement Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "spec",
        type=str,
        help="Path to memory specification JSON file"
    )
    
    parser.add_argument(
        "workload",
        type=str,
        help="Path to workload JSON file"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output JSON file for results"
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output (only print errors)"
    )
    
    args = parser.parse_args()
    
    # Load specification
    try:
        spec = MemorySpec.from_json(args.spec)
    except Exception as e:
        print(f"Error loading specification: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Load workload
    try:
        workload = Workload.from_json(args.workload)
    except Exception as e:
        print(f"Error loading workload: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Run simulation
    simulator = Simulator(spec)
    result = simulator.simulate(workload)
    
    # Print results
    if not args.quiet:
        print_results(result, simulator)
    
    # Export if requested
    if args.output:
        try:
            export_json(result, args.output)
        except Exception as e:
            print(f"Error exporting results: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Exit with error code if there were errors
    if simulator.get_errors():
        sys.exit(1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()

