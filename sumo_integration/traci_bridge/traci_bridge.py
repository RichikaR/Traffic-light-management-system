"""
TraCI Bridge — TLMOS Hybrid Kernel ↔ SUMO
==========================================
This is the heart of the SUMO integration.

What it does:
  Every simulation second, this bridge:
    1. Reads real queue lengths and wait times from SUMO via TraCI
    2. Feeds them into the HybridKernel (your existing Python kernel)
    3. Receives the kernel's phase decision
    4. Sends green/red commands back to SUMO via TraCI

Your HybridKernel code is UNCHANGED. The bridge is just a data adapter
that replaces the fake Poisson arrivals with real SUMO ground truth.

Architecture:
                    ┌─────────────────────────┐
                    │  SUMO Physics Engine     │
                    │  - Krauss car-following  │
                    │  - Lane changing         │
                    │  - Real vehicle agents   │
                    └──────────┬──────────────┘
                               │ TraCI socket (localhost:8813)
                    ┌──────────▼──────────────┐
                    │   TLMOSTraCIBridge       │  ← this file
                    │   - reads lane data      │
                    │   - adapts to Lane objs  │
                    │   - writes phase cmds    │
                    └──────────┬──────────────┘
                               │ Python function calls
                    ┌──────────▼──────────────┐
                    │   HybridKernel           │  ← your existing kernel
                    │   P_s = α·MP + β·WFQ    │
                    │   WFG deadlock detect    │
                    └─────────────────────────┘

Usage:
    python sumo_integration/traci_bridge/traci_bridge.py \
        --config sumo_integration/demand/generated/morning_peak.sumocfg \
        --gui
"""

import os
import sys
import traci
import traci.constants as tc
from typing import Dict, List, Tuple, Optional

# Add repo root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from simulation.kernel.hybrid_scheduler import HybridKernel, Lane, Phase


# ---------------------------------------------------------------------------
# SUMO phase → TLMOS phase mapping
# ---------------------------------------------------------------------------

def parse_sumo_phases(tls_id: str) -> Tuple[List[Phase], Dict[str, str]]:
    """
    Read the signal program from SUMO and construct TLMOS Phase objects.

    SUMO phase strings look like: "GGrrGGrr" (G=green, r=red, y=yellow)
    We group non-yellow phases into TLMOS Phase objects.

    Returns:
        phases      : list of Phase objects for the HybridKernel
        phase_index : maps phase_id → SUMO phase index string
    """
    logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
    sumo_phases = logic.phases

    # Get controlled lanes
    controlled_links = traci.trafficlight.getControlledLinks(tls_id)
    # controlled_links[i] = list of (from_lane, to_lane, via_lane) for signal i

    tlmos_phases = []
    phase_map = {}   # phase_id → SUMO phase index

    sumo_phase_idx = 0
    tlmos_phase_num = 0

    for sp in sumo_phases:
        state = sp.state
        # Skip yellow/all-red phases (TLMOS handles these internally)
        if all(c in "yrR" for c in state):
            continue

        # Collect movements served in this phase (signal = 'G' or 'g')
        movements = []
        for signal_idx, signal_state in enumerate(state):
            if signal_state in ("G", "g") and signal_idx < len(controlled_links):
                links = controlled_links[signal_idx]
                for link in links:
                    if len(link) >= 2:
                        from_lane = link[0]
                        to_lane   = link[1]
                        movements.append((from_lane, to_lane))

        if not movements:
            continue

        phase_id = f"phase_{tlmos_phase_num}"
        tlmos_phases.append(Phase(
            phase_id=phase_id,
            movements=movements,
            min_green=float(sp.minDur) if hasattr(sp, "minDur") and sp.minDur > 0 else 7.0,
            max_green=float(sp.maxDur) if hasattr(sp, "maxDur") and sp.maxDur > 0 else 55.0,
        ))
        phase_map[phase_id] = sumo_phase_idx
        tlmos_phase_num += 1
        sumo_phase_idx += 1

    # Fallback: if SUMO phases are weird, create a simple 2-phase plan
    if not tlmos_phases:
        tlmos_phases = [
            Phase("phase_0", [], min_green=7.0, max_green=55.0),
            Phase("phase_1", [], min_green=7.0, max_green=55.0),
        ]

    return tlmos_phases, phase_map


# ---------------------------------------------------------------------------
# Lane data reader from SUMO
# ---------------------------------------------------------------------------

def read_sumo_lane_data(lane_ids: List[str]) -> Dict[str, Lane]:
    """
    Read current queue lengths and wait times for all lanes from SUMO.
    This replaces the Poisson arrival generator in run_benchmarks.py.
    """
    lanes = {}
    for lid in lane_ids:
        try:
            queue    = traci.lane.getLastStepHaltingNumber(lid)
            # Head-of-queue wait: max waiting time among halted vehicles
            vehicles = traci.lane.getLastStepVehicleIDs(lid)
            max_wait = 0.0
            for veh in vehicles:
                w = traci.vehicle.getWaitingTime(veh)
                if w > max_wait:
                    max_wait = w

            # Saturation flow from lane speed limit (veh/hr = speed_ms * 2000 heuristic)
            speed = traci.lane.getMaxSpeed(lid)
            sat_flow = max(600.0, min(1800.0, speed * 2000))

            lanes[lid] = Lane(
                lane_id=lid,
                queue=queue,
                head_wait_time=max_wait,
                saturation_flow=sat_flow,
            )
        except traci.exceptions.TraCIException:
            pass  # lane may not exist in current timestep

    return lanes


# ---------------------------------------------------------------------------
# Phase command sender to SUMO
# ---------------------------------------------------------------------------

def send_phase_to_sumo(tls_id: str, phase_id: str, phase_map: Dict[str, str],
                       yellow_time: float = 3.0):
    """
    Send the kernel's phase decision to SUMO.
    SUMO's setPhase() takes a phase index integer.
    """
    if phase_id not in phase_map:
        return
    sumo_phase_idx = phase_map[phase_id]
    try:
        traci.trafficlight.setPhase(tls_id, sumo_phase_idx)
        # Tell SUMO how long to hold this phase
        traci.trafficlight.setPhaseDuration(tls_id, 999)  # kernel controls duration
    except traci.exceptions.TraCIException as e:
        pass   # junction may not be active yet


# ---------------------------------------------------------------------------
# Main TraCI Bridge class
# ---------------------------------------------------------------------------

class TLMOSTraCIBridge:
    """
    Connects one TLMOS HybridKernel instance to one SUMO TLS junction.
    For multi-intersection grids, instantiate one bridge per junction.
    """

    def __init__(
        self,
        tls_id: str,
        alpha: float = 0.7,
        beta: float = 0.3,
        yellow_time: float = 3.0,
        control_interval: float = 1.0,
    ):
        self.tls_id = tls_id
        self.yellow_time = yellow_time
        self.control_interval = control_interval

        # Build phases from SUMO signal program
        phases, self.phase_map = parse_sumo_phases(tls_id)

        # Get all controlled lane IDs
        controlled = traci.trafficlight.getControlledLinks(tls_id)
        lane_ids = list({lnk[0] for links in controlled for lnk in links if links})
        self.lane_ids = lane_ids

        # Read initial lane state
        lanes = read_sumo_lane_data(lane_ids)

        # Ensure all phases reference existing lanes
        all_lane_ids = set(lanes.keys())
        for phase in phases:
            phase.movements = [(u, d) for u, d in phase.movements
                               if u in all_lane_ids]

        # Downstream lane mapping for WFG
        for phase in phases:
            for (uid, did) in phase.movements:
                if uid in lanes and did in all_lane_ids:
                    lanes[uid].downstream_lane_id = did

        # Instantiate the Hybrid Kernel
        self.kernel = HybridKernel(
            lanes=lanes,
            phases=phases,
            alpha=alpha,
            beta=beta,
            yellow_time=yellow_time,
            control_interval=control_interval,
        )

        # Metric logging
        self.step_count = 0
        self.metric_log: List[Dict] = []

    def step(self):
        """
        Called every SUMO simulation second.
        Reads real data from SUMO, runs kernel, sends command back.
        """
        # 1. Read ground-truth lane data from SUMO
        sumo_lanes = read_sumo_lane_data(self.lane_ids)

        # 2. Sync kernel lanes with SUMO reality
        #    (replace fake queues with real SUMO queues)
        for lid, sumo_lane in sumo_lanes.items():
            if lid in self.kernel.lanes:
                self.kernel.lanes[lid].queue          = sumo_lane.queue
                self.kernel.lanes[lid].head_wait_time = sumo_lane.head_wait_time
            else:
                self.kernel.lanes[lid] = sumo_lane

        # 3. Run kernel step (no arrivals needed — SUMO handles vehicle insertion)
        self.kernel.step(arrivals=None)

        # 4. Send phase decision to SUMO
        send_phase_to_sumo(
            self.tls_id,
            self.kernel.current_phase.phase_id,
            self.phase_map,
            self.yellow_time,
        )

        self.step_count += 1

        # 5. Log every 60 steps for plotting
        if self.step_count % 60 == 0:
            m = self.kernel.get_metrics()
            m["sim_time"] = self.step_count
            self.metric_log.append(m)

    def get_metrics(self) -> Dict:
        return self.kernel.get_metrics()