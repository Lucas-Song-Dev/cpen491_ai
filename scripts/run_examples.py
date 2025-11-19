#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run multiple example simulations and generate a pretty formatted report.
"""

import sys
import json
import os
from pathlib import Path
from typing import List, Dict, Any

# Set UTF-8 encoding for output (works on Linux/Mac, fallback on Windows)
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Python < 3.7 or encoding not available, use ASCII fallbacks
        pass

# Add parent directory to path to allow imports
base_dir = Path(__file__).parent.parent
sys.path.insert(0, str(base_dir))

from ddr5_power_tool.spec_parser import MemorySpec
from ddr5_power_tool.workload_parser import Workload
from ddr5_power_tool.simulator import Simulator


# Define 4 example configurations
EXAMPLES = [
    {
        "name": "DDR5 Simple Workload",
        "description": "Basic DDR5 workload with activate, read, write, and precharge operations",
        "spec": "examples/ddr5_6400_spec.json",
        "workload": "examples/simple_workload.json"
    },
    {
        "name": "DDR5 Sequential Access",
        "description": "Sequential access pattern with high row buffer hit rate",
        "spec": "examples/ddr5_6400_spec.json",
        "workload": "examples/sequential_workload.json"
    },
    {
        "name": "DDR5 Random Access",
        "description": "Random access pattern across multiple banks with frequent precharges",
        "spec": "examples/ddr5_6400_spec.json",
        "workload": "examples/random_workload.json"
    },
    {
        "name": "DDR5 Refresh Heavy",
        "description": "Workload with frequent refresh operations to test refresh power impact",
        "spec": "examples/ddr5_6400_spec.json",
        "workload": "examples/refresh_heavy_workload.json"
    }
]


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


def format_time(time_ns: float) -> str:
    """Format time value."""
    if time_ns >= 1e6:
        return f"{time_ns / 1e6:.3f} ms"
    elif time_ns >= 1e3:
        return f"{time_ns / 1e3:.3f} µs"
    else:
        return f"{time_ns:.3f} ns"


def print_example_result(example: Dict[str, Any], result, simulator: Simulator, index: int):
    """Print formatted result for a single example."""
    print("\n" + "="*80)
    print(f"Example {index + 1}: {example['name']}")
    print("="*80)
    print(f"Description: {example['description']}")
    print(f"Specification: {example['spec']}")
    print(f"Workload: {example['workload']}")
    print("-"*80)
    
    print(f"\n[RESULTS] Simulation Results:")
    print(f"  Simulation Time:     {format_time(result.simulation_time)}")
    print(f"  Average Power:       {format_power(result.average_power)}")
    print(f"  Total Energy:        {format_energy(result.total_energy)}")
    
    print(f"\n[CORE] Core Energy Breakdown:")
    print(f"  Activation:          {format_energy(result.activation_energy)}")
    print(f"  Read Operations:     {format_energy(result.read_energy)}")
    print(f"  Write Operations:    {format_energy(result.write_energy)}")
    print(f"  Precharge:           {format_energy(result.precharge_energy)}")
    print(f"  Refresh:             {format_energy(result.refresh_energy)}")
    print(f"  Background (Active): {format_energy(result.background_active_energy)}")
    print(f"  Background (Idle):  {format_energy(result.background_precharge_energy)}")
    print(f"  Power-Down:          {format_energy(result.powerdown_energy)}")
    print(f"  " + "-" * 60)
    print(f"  Core Total:          {format_energy(result.core_energy)}")
    
    print(f"\n[IO] Interface Energy Breakdown:")
    print(f"  Termination (ODT):   {format_energy(result.termination_energy)}")
    print(f"  Dynamic I/O:         {format_energy(result.dynamic_io_energy)}")
    print(f"  " + "-" * 60)
    print(f"  Interface Total:     {format_energy(result.interface_energy)}")
    
    # Calculate percentages
    if result.total_energy > 0:
        core_pct = (result.core_energy / result.total_energy) * 100
        interface_pct = (result.interface_energy / result.total_energy) * 100
        print(f"\n[STATS] Energy Distribution:")
        print(f"  Core Power:         {core_pct:.1f}%")
        print(f"  Interface Power:   {interface_pct:.1f}%")
    
    errors = simulator.get_errors()
    warnings = simulator.get_warnings()
    
    if errors:
        print(f"\n[ERROR] Errors ({len(errors)}):")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print(f"\n[WARN] Warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print(f"\n[OK] Simulation completed successfully!")


def generate_summary_table(results: List[Dict[str, Any]]):
    """Generate a summary table of all results."""
    print("\n" + "="*80)
    print("SUMMARY TABLE")
    print("="*80)
    print(f"{'Example':<30} {'Time':<15} {'Power (mW)':<15} {'Energy (nJ)':<15}")
    print("-"*80)
    
    for i, res in enumerate(results):
        example = res['example']
        result = res['result']
        name = example['name'][:28]  # Truncate if too long
        time_str = format_time(result.simulation_time)
        power_str = f"{result.average_power:.2f}"
        energy_str = f"{result.total_energy:.2f}"
        print(f"{name:<30} {time_str:<15} {power_str:<15} {energy_str:<15}")
    
    print("="*80)


def main():
    """Run all examples and generate report."""
    # base_dir is already set at module level
    
    print("="*80)
    print("DDR5/LPDDR5 Power Measurement Tool - Example Simulations")
    print("="*80)
    print(f"Running {len(EXAMPLES)} example configurations...\n")
    
    results = []
    
    for i, example in enumerate(EXAMPLES):
        spec_path = base_dir / example["spec"]
        workload_path = base_dir / example["workload"]
        
        if not spec_path.exists():
            print(f"[ERROR] Specification file not found: {spec_path}", file=sys.stderr)
            continue
        
        if not workload_path.exists():
            print(f"[ERROR] Workload file not found: {workload_path}", file=sys.stderr)
            continue
        
        try:
            # Load specification and workload
            spec = MemorySpec.from_json(str(spec_path))
            workload = Workload.from_json(str(workload_path))
            
            # Run simulation
            simulator = Simulator(spec)
            result = simulator.simulate(workload)
            
            # Store result
            results.append({
                "example": example,
                "result": result,
                "simulator": simulator
            })
            
            # Print result
            print_example_result(example, result, simulator, i)
            
        except Exception as e:
            print(f"\n[ERROR] Error running {example['name']}: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            continue
    
    # Generate summary
    if results:
        generate_summary_table(results)
        
        # Calculate statistics
        if len(results) > 0:
            avg_power = sum(r['result'].average_power for r in results) / len(results)
            total_energy = sum(r['result'].total_energy for r in results)
            print(f"\n[STATS] Overall Statistics:")
            print(f"  Average Power (across examples): {format_power(avg_power)}")
            print(f"  Total Energy (all examples):      {format_energy(total_energy)}")
    
    print("\n" + "="*80)
    print("All examples completed!")
    print("="*80)
    
    # Exit with error code if any simulations had errors
    has_errors = any(len(r['simulator'].get_errors()) > 0 for r in results)
    sys.exit(1 if has_errors else 0)


if __name__ == "__main__":
    main()

