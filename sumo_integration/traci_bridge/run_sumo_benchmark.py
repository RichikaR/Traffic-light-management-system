"""
SUMO Benchmark Runner
======================
Runs the full 4-controller comparison inside SUMO with real vehicle physics.
This is the publication-grade replacement for run_benchmarks.py.

Usage:
    # Quick single run
    python sumo_integration/traci_bridge/run_sumo_benchmark.py \
        --config sumo_integration/demand/generated/morning_peak.sumocfg

    # Full benchmark with GUI (watch the simulation)
    python sumo_integration/traci_bridge/run_sumo_benchmark.py \
        --config sumo_integration/demand/generated/morning_peak.sumocfg \
        --gui

    # All scenarios headless (for paper results)
    python sumo_integration/traci_bridge/run_sumo_benchmark.py --all

Outputs:
    metrics_output/sumo_results.csv
    metrics_output/sumo_plots/
"""

import os
import sys
import csv
import copy
import subprocess
import argparse
from typing import Dict, List, Optional

import traci
import traci.constants as tc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from simulation.kernel.hybrid_scheduler import HybridKernel, Lane, Phase
from simulation.baselines.controllers import (
    FixedTimeController, ActuatedController, MaxPressureController
)
from sumo_integration.traci_bridge.traci_bridge import TLMOSTraCIBridge

DEMAND_DIR   = os.path.join(os.path.dirname(__file__), "..", "demand", "generated")
OUTPUT_DIR   = os.path.join(os.path.dirname(__file__), "..", "..", "metrics_output")
SUMO_PORT    = 8813


# ---------------------------------------------------------------------------
# Baseline wrappers that work via TraCI
# (same interface as TLMOSTraCIBridge but different scheduling logic)
# ---------------------------------------------------------------------------

class FixedTimeTraCIBridge:
    def __init__(self, tls_id: str, cycle_length: float = 90.0, yellow_time: float = 3.0):
        self.tls_id = tls_id
        self.yellow_time = yellow_time
        # Get all phases from SUMO, filter to green phases only
        logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
        self.all_phases = logic.phases
        self.green_indices = [i for i, p in enumerate(self.all_phases)
                              if any(c in "Gg" for c in p.state)
                              and not all(c in "yrR" for c in p.state)]
        n = len(self.green_indices)
        effective = cycle_length - n * yellow_time
        self.green_time = max(7.0, effective / max(n, 1))
        self.current_idx = 0
        self.elapsed = 0.0
        self.total_veh_seconds = 0
        self.total_departed = 0
        self.context_switches = 0
        self.step_count = 0
        # Force SUMO to first green phase
        if self.green_indices:
            traci.trafficlight.setPhase(tls_id, self.green_indices[0])
            traci.trafficlight.setPhaseDuration(tls_id, int(self.green_time))

    def step(self):
        self.elapsed += 1.0
        self.step_count += 1
        # Accumulate delay
        for lane in traci.trafficlight.getControlledLanes(self.tls_id):
            self.total_veh_seconds += traci.lane.getLastStepHaltingNumber(lane)
        self.total_departed += traci.simulation.getArrivedNumber()
        # Switch phase at end of green_time
        if self.elapsed >= self.green_time and self.green_indices:
            self.current_idx = (self.current_idx + 1) % len(self.green_indices)
            traci.trafficlight.setPhase(self.tls_id, self.green_indices[self.current_idx])
            traci.trafficlight.setPhaseDuration(self.tls_id, int(self.green_time))
            self.elapsed = 0.0
            self.context_switches += 1

    def get_metrics(self):
        avg = round(self.total_veh_seconds / max(self.total_departed, 1), 2)
        return {"avg_delay_s_per_veh": avg,
                "context_switch_count": self.context_switches,
                "flush_events": 0, "split_failures": 0,
                "simulation_steps": self.step_count,
                "total_veh_seconds": self.total_veh_seconds,
                "total_departed": self.total_departed}


class ActuatedTraCIBridge:
    def __init__(self, tls_id: str, gap_threshold: float = 3.0, yellow_time: float = 3.0):
        self.tls_id = tls_id
        self.yellow_time = yellow_time
        self.gap_threshold = gap_threshold
        logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
        self.all_phases = logic.phases
        self.green_indices = [i for i, p in enumerate(self.all_phases)
                              if any(c in "Gg" for c in p.state)
                              and not all(c in "yrR" for c in p.state)]
        self.current_idx = 0
        self.elapsed = 0.0
        self.gap_timer = 0.0
        self.min_green = 7.0
        self.max_green = 55.0
        self.total_veh_seconds = 0
        self.total_departed = 0
        self.context_switches = 0
        self.split_failures = 0
        self.step_count = 0
        if self.green_indices:
            traci.trafficlight.setPhase(tls_id, self.green_indices[0])
            traci.trafficlight.setPhaseDuration(tls_id, int(self.max_green))

    def step(self):
        self.elapsed += 1.0
        self.step_count += 1
        for lane in traci.trafficlight.getControlledLanes(self.tls_id):
            self.total_veh_seconds += traci.lane.getLastStepHaltingNumber(lane)
        self.total_departed += traci.simulation.getArrivedNumber()
        if not self.green_indices:
            return
        # Check if current phase lanes have active vehicles
        current_phase_idx = self.green_indices[self.current_idx]
        current_state = self.all_phases[current_phase_idx].state
        controlled = traci.trafficlight.getControlledLanes(self.tls_id)
        active = False
        for i, lane in enumerate(controlled):
            if i < len(current_state) and current_state[i] in "Gg":
                if traci.lane.getLastStepHaltingNumber(lane) > 0:
                    active = True
                    break
        if active:
            self.gap_timer = 0.0
        else:
            self.gap_timer += 1.0
        gap_out = self.gap_timer >= self.gap_threshold and self.elapsed >= self.min_green
        max_out = self.elapsed >= self.max_green
        if gap_out or max_out:
            if max_out:
                self.split_failures += 1
            self.current_idx = (self.current_idx + 1) % len(self.green_indices)
            traci.trafficlight.setPhase(self.tls_id, self.green_indices[self.current_idx])
            traci.trafficlight.setPhaseDuration(self.tls_id, int(self.max_green))
            self.elapsed = 0.0
            self.gap_timer = 0.0
            self.context_switches += 1

    def get_metrics(self):
        avg = round(self.total_veh_seconds / max(self.total_departed, 1), 2)
        return {"avg_delay_s_per_veh": avg,
                "context_switch_count": self.context_switches,
                "flush_events": 0, "split_failures": self.split_failures,
                "simulation_steps": self.step_count,
                "total_veh_seconds": self.total_veh_seconds,
                "total_departed": self.total_departed}

def _blank_metrics():
    return {
        "avg_delay_s_per_veh": 0.0,
        "total_veh_seconds": 0,
        "total_departed": 0,
        "context_switch_count": 0,
        "flush_events": 0,
        "split_failures": 0,
    }


# ---------------------------------------------------------------------------
# Run one controller inside SUMO
# ---------------------------------------------------------------------------

def run_sumo_controller(
    config_file: str,
    tls_id: str,
    controller_name: str,
    use_gui: bool = False,
    port: int = SUMO_PORT,
) -> Dict:
    """
    Start SUMO, run one controller for the full duration, return metrics.
    """
    sumo_binary = "sumo-gui" if use_gui else "sumo"
    sumo_cmd = [
        sumo_binary,
        "-c", config_file,
        "--no-step-log", "true",
        "--no-warnings",  "true",
        "--quit-on-end",  "true",
    ]

    traci.start(sumo_cmd, port=port)

    try:
        # Build controller
        if controller_name == "TLMOS":
            bridge = TLMOSTraCIBridge(tls_id, alpha=0.7, beta=0.3)
        elif controller_name == "Fixed-Time":
            bridge = FixedTimeTraCIBridge(tls_id)
        elif controller_name == "Actuated":
            bridge = ActuatedTraCIBridge(tls_id)
        elif controller_name == "Max-Pressure":
            # MP = TLMOS with beta=0
            bridge = TLMOSTraCIBridge(tls_id, alpha=1.0, beta=0.0)
        else:
            raise ValueError(f"Unknown controller: {controller_name}")

        delay_trace = []
        step = 0

        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()
            bridge.step()
            step += 1

            # Track departed vehicles
            departed = traci.simulation.getArrivedNumber()
            if hasattr(bridge, "_metrics"):
                bridge._metrics["total_departed"] += departed
            elif hasattr(bridge, "kernel"):
                bridge.kernel.total_departed += departed

            if step % 60 == 0:
                m = bridge.get_metrics()
                delay_trace.append((step, m.get("avg_delay_s_per_veh", 0)))

        metrics = bridge.get_metrics()
        metrics["delay_trace"] = delay_trace
        metrics["simulation_steps"] = step
        return metrics

    finally:
        traci.close()


# ---------------------------------------------------------------------------
# Full benchmark: 4 controllers × N scenarios
# ---------------------------------------------------------------------------

def run_full_benchmark(config_files: Dict[str, str], use_gui: bool = False):
    """
    config_files: {scenario_name: path_to_.sumocfg}
    """
    controllers = ["Fixed-Time", "Actuated", "Max-Pressure", "TLMOS"]
    all_results = {}

    for scenario_name, config_file in config_files.items():
        print(f"\n▶ Scenario: {scenario_name}")
        ctrl_results = {}

        # Get the first TLS junction ID from the network
        traci.start(["sumo", "-c", config_file,
                     "--no-warnings", "true"], port=SUMO_PORT+1)
        tls_ids = traci.trafficlight.getIDList()
        traci.close()

        if not tls_ids:
            print(f"  No TLS junctions found in {config_file}, skipping.")
            continue

        tls_id = tls_ids[0]  # use first junction; extend to all for grid scenario
        print(f"  TLS junction: {tls_id}")

        for ctrl_name in controllers:
            print(f"  • {ctrl_name}...", end="", flush=True)
            try:
                metrics = run_sumo_controller(
                    config_file=config_file,
                    tls_id=tls_id,
                    controller_name=ctrl_name,
                    use_gui=(use_gui and ctrl_name == "TLMOS"),
                    port=SUMO_PORT,
                )
                ctrl_results[ctrl_name] = metrics
                print(f" avg_delay={metrics.get('avg_delay_s_per_veh','?')}s ✓")
            except Exception as e:
                print(f" ERROR: {e}")
                ctrl_results[ctrl_name] = {}

        all_results[scenario_name] = ctrl_results
        _print_table(scenario_name, ctrl_results)

    _export_csv(all_results, os.path.join(OUTPUT_DIR, "sumo_results.csv"))
    _generate_plots(all_results, os.path.join(OUTPUT_DIR, "sumo_plots"))
    return all_results


# ---------------------------------------------------------------------------
# Output helpers (same as run_benchmarks.py)
# ---------------------------------------------------------------------------

METRIC_LABELS = {
    "avg_delay_s_per_veh":   "Avg Delay (s/veh)",
    "context_switch_count":  "Phase Changes",
    "flush_events":          "Flush Events (TLMOS only)",
    "split_failures":        "Split Failures",
    "simulation_steps":      "Sim Steps",
}

def _print_table(scenario: str, results: Dict):
    cnames = list(results.keys())
    print(f"\n{'='*72}\n  SUMO Results — {scenario.upper()}\n{'='*72}")
    header = f"{'Metric':<34}" + "".join(f"{n:>12}" for n in cnames)
    print(header)
    print("-" * 72)
    for key, label in METRIC_LABELS.items():
        row = f"{label:<34}"
        for c in cnames:
            val = results[c].get(key, "-")
            row += f"{str(val):>12}"
        print(row)
    print()

def _export_csv(all_results: Dict, path: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    rows = []
    for scenario, ctrl_results in all_results.items():
        for ctrl, metrics in ctrl_results.items():
            row = {"scenario": scenario, "controller": ctrl}
            for k, v in metrics.items():
                if k != "delay_trace":
                    row[k] = v
            rows.append(row)
    if not rows:
        return
    # Collect ALL field names across all rows to handle varying metrics
    all_fields = list(dict.fromkeys(
        k for row in rows for k in row.keys()
    ))
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n✓ SUMO results → {path}")
def _generate_plots(all_results: Dict, plot_dir: str):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    os.makedirs(plot_dir, exist_ok=True)
    colors = {"Fixed-Time": "#e74c3c", "Actuated": "#f39c12",
              "Max-Pressure": "#3498db", "TLMOS": "#27ae60"}

    for scenario, ctrl_results in all_results.items():
        cnames = list(ctrl_results.keys())
        delays = [ctrl_results[c].get("avg_delay_s_per_veh", 0) for c in cnames]

        fig, ax = plt.subplots(figsize=(8, 5))
        bars = ax.bar(cnames, delays,
                      color=[colors.get(c, "#95a5a6") for c in cnames],
                      edgecolor="white")
        for b, name in zip(bars, cnames):
            if name == "TLMOS":
                b.set_edgecolor("#1a252f"); b.set_linewidth(2.5)

        ax.set_title(f"SUMO Average Delay — {scenario.replace('_', ' ').title()}", fontsize=13)
        ax.set_ylabel("Avg Delay (s/veh)", fontsize=11)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        plt.savefig(os.path.join(plot_dir, f"sumo_delay_{scenario}.png"), dpi=150)
        plt.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TLMOS SUMO Benchmark")
    parser.add_argument("--config", type=str, default=None,
                        help="Path to a single .sumocfg file")
    parser.add_argument("--scenario", type=str, default="morning_peak",
                        help="Scenario name (used as label)")
    parser.add_argument("--all", action="store_true",
                        help="Run all generated scenarios")
    parser.add_argument("--gui", action="store_true",
                        help="Open sumo-gui for TLMOS run")
    args = parser.parse_args()

    if args.all:
        # Find all .sumocfg files in the generated demand folder
        configs = {}
        if os.path.exists(DEMAND_DIR):
            for f in os.listdir(DEMAND_DIR):
                if f.endswith(".sumocfg"):
                    name = f.replace(".sumocfg", "")
                    configs[name] = os.path.join(DEMAND_DIR, f)
        if not configs:
            print("No .sumocfg files found. Run generate_demand.py first.")
            sys.exit(1)
    elif args.config:
        configs = {args.scenario: args.config}
    else:
        parser.print_help()
        sys.exit(1)

    run_full_benchmark(configs, use_gui=args.gui)