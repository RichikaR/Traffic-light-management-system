"""
Traffic Scenarios
=================
Defines reusable intersection topologies and demand profiles.
Arrivals follow a Poisson process (standard in queueing theory for traffic).

Scenarios
---------
- single_intersection_moderate  : 4-way intersection, v/c ≈ 0.6
- single_intersection_saturated : 4-way intersection, v/c ≈ 0.95 (rush hour)
- asymmetric_demand             : heavy arterial + light side-street (starvation test)
- deadlock_scenario             : engineered gridlock condition for WFG validation
"""

from __future__ import annotations
import random
from typing import Dict, Tuple, List
from simulation.kernel.hybrid_scheduler import Lane, Phase


# ---------------------------------------------------------------------------
# Topology builder
# ---------------------------------------------------------------------------

def build_single_intersection() -> Tuple[Dict[str, Lane], List[Phase]]:
    """
    4-approach, 2-phase intersection.
    Phases:
      Phase A: North↔South (through + left)
      Phase B: East↔West   (through + left)

    Lane naming: {direction}_{movement}
      N_thru = Northbound through, E_left = Eastbound left-turn, etc.
    Downstream lanes represent where vehicles exit to.
    """
    lanes = {
        # Northbound approach
        "N_thru": Lane("N_thru", downstream_lane_id="S_thru", saturation_flow=1800),
        "N_left": Lane("N_left", downstream_lane_id="W_thru", saturation_flow=1500),
        # Southbound approach
        "S_thru": Lane("S_thru", downstream_lane_id="N_thru", saturation_flow=1800),
        "S_left": Lane("S_left", downstream_lane_id="E_thru", saturation_flow=1500),
        # Eastbound approach
        "E_thru": Lane("E_thru", downstream_lane_id="W_thru", saturation_flow=1800),
        "E_left": Lane("E_left", downstream_lane_id="S_thru", saturation_flow=1500),
        # Westbound approach
        "W_thru": Lane("W_thru", downstream_lane_id="E_thru", saturation_flow=1800),
        "W_left": Lane("W_left", downstream_lane_id="N_thru", saturation_flow=1500),
    }

    phases = [
        Phase(
            phase_id="A",
            movements=[("N_thru", "S_thru"), ("N_left", "W_thru"),
                       ("S_thru", "N_thru"), ("S_left", "E_thru")],
            min_green=7.0,
            max_green=55.0,
        ),
        Phase(
            phase_id="B",
            movements=[("E_thru", "W_thru"), ("E_left", "S_thru"),
                       ("W_thru", "E_thru"), ("W_left", "N_thru")],
            min_green=7.0,
            max_green=55.0,
        ),
    ]
    return lanes, phases


# ---------------------------------------------------------------------------
# Demand generators (Poisson arrivals)
# ---------------------------------------------------------------------------

def poisson_arrivals(rates: Dict[str, float], dt: float = 1.0) -> Dict[str, int]:
    """
    Generate stochastic arrivals for each lane.
    rates: {lane_id: vehicles_per_second}
    Returns integer vehicle counts drawn from Poisson distribution.
    """
    return {
        lid: _poisson(rate * dt)
        for lid, rate in rates.items()
    }

def _poisson(lam: float) -> int:
    """Simple Poisson random variate (Knuth algorithm)."""
    if lam <= 0:
        return 0
    import math
    L = math.exp(-lam)
    k, p = 0, 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


# ---------------------------------------------------------------------------
# Named demand profiles
# ---------------------------------------------------------------------------

# Rates in vehicles/second per lane

MODERATE_DEMAND = {   # v/c ≈ 0.60
    "N_thru": 0.20, "N_left": 0.05,
    "S_thru": 0.20, "S_left": 0.05,
    "E_thru": 0.20, "E_left": 0.05,
    "W_thru": 0.20, "W_left": 0.05,
}

SATURATED_DEMAND = {  # v/c ≈ 0.95 (rush hour stress test)
    "N_thru": 0.42, "N_left": 0.10,
    "S_thru": 0.42, "S_left": 0.10,
    "E_thru": 0.42, "E_left": 0.10,
    "W_thru": 0.42, "W_left": 0.10,
}

ASYMMETRIC_DEMAND = { # Heavy N-S arterial, light E-W side street (starvation test)
    "N_thru": 0.40, "N_left": 0.08,
    "S_thru": 0.40, "S_left": 0.08,
    "E_thru": 0.06, "E_left": 0.02,  # ← minor street
    "W_thru": 0.06, "W_left": 0.02,  # ← minor street
}

DEADLOCK_DEMAND = {   # Engineered near-saturation to trigger WFG cycle
    "N_thru": 0.48, "N_left": 0.12,
    "S_thru": 0.48, "S_left": 0.12,
    "E_thru": 0.48, "E_left": 0.12,
    "W_thru": 0.48, "W_left": 0.12,
}

SCENARIOS = {
    "moderate":    MODERATE_DEMAND,
    "saturated":   SATURATED_DEMAND,
    "asymmetric":  ASYMMETRIC_DEMAND,
    "deadlock":    DEADLOCK_DEMAND,
}