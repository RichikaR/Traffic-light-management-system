"""
Baseline Traffic Signal Controllers
=====================================
Three baselines against which TLMOS is benchmarked:

1. FixedTime    — Webster's method (pre-timed, no sensing)
2. Actuated     — sensor-based green extension (industry standard)
3. MaxPressure  — pure Tassiulas & Ephremides (no fairness term, beta=0)

All controllers share the same Lane/Phase interface as HybridKernel so
they can be swapped into run_benchmarks.py without modification.
"""

from __future__ import annotations
from typing import Dict, List, Optional
from simulation.kernel.hybrid_scheduler import Lane, Phase


# ---------------------------------------------------------------------------
# 1. Fixed-Time Controller (Webster, 1958)
# ---------------------------------------------------------------------------

class FixedTimeController:
    """
    Pre-timed controller. Phases rotate on a fixed cycle.
    Cycle length computed via Webster's formula:
        C* = (1.5*L + 5) / (1 - Y)
    where L = total lost time, Y = sum of critical flow ratios.
    This is the 'null hypothesis' baseline.
    """

    def __init__(
        self,
        lanes: Dict[str, Lane],
        phases: List[Phase],
        cycle_length: float = 90.0,   # seconds (Webster-optimised for moderate flow)
        yellow_time: float = 3.0,
        control_interval: float = 1.0,
    ):
        self.lanes = lanes
        self.phases = phases
        self.yellow_time = yellow_time
        self.control_interval = control_interval
        self.cycle_length = cycle_length

        # Distribute green equally across phases (simplified Webster split)
        n = len(phases)
        effective_green = cycle_length - n * yellow_time
        self.green_times = [max(effective_green / n, 5.0) for _ in phases]

        self.phase_idx = 0
        self.elapsed = 0.0
        self.in_yellow = False
        self.yellow_elapsed = 0.0
        self.time = 0.0

        # Metrics
        self.total_delay = 0.0
        self.total_departed = 0
        self.total_arrivals = 0
        self.context_switches = 0
        self.split_failures = 0
        self.idle_veh_seconds = 0.0
        self.fairness_samples: List[float] = []

    @property
    def current_phase(self) -> Phase:
        return self.phases[self.phase_idx]

    def process_arrivals(self, arrivals: Dict[str, int]):
        for lid, n in arrivals.items():
            if lid in self.lanes:
                self.lanes[lid].arrival(n)
                self.total_arrivals += n

    def step(self, arrivals: Optional[Dict[str, int]] = None):
        dt = self.control_interval
        self.time += dt

        if arrivals:
            self.process_arrivals(arrivals)

        for lane in self.lanes.values():
            lane.tick(dt)
            self.total_delay += lane.queue * dt
            self.idle_veh_seconds += lane.queue * dt

        if self.in_yellow:
            self.yellow_elapsed += dt
            if self.yellow_elapsed >= self.yellow_time:
                self.in_yellow = False
                self.yellow_elapsed = 0.0
                self.phase_idx = (self.phase_idx + 1) % len(self.phases)
                self.elapsed = 0.0
            return

        # Serve current phase
        for uid, _ in self.current_phase.movements:
            lane = self.lanes.get(uid)
            if lane and lane.queue > 0:
                cap = max(1, int(lane.saturation_flow / 3600.0 * dt))
                d = lane.departure(cap)
                self.total_departed += d

        self.elapsed += dt

        # Check split failure
        if self.elapsed >= self.green_times[self.phase_idx]:
            for uid, _ in self.current_phase.movements:
                if self.lanes.get(uid) and self.lanes[uid].queue > 0:
                    self.split_failures += 1

        # Switch phase at end of green
        if self.elapsed >= self.green_times[self.phase_idx]:
            self.in_yellow = True
            self.yellow_elapsed = 0.0
            self.context_switches += 1

        delays = [l.head_wait_time for l in self.lanes.values() if l.queue > 0]
        if delays:
            n = len(delays)
            jain = (sum(delays) ** 2) / (n * sum(d ** 2 for d in delays))
            self.fairness_samples.append(jain)

    def get_metrics(self) -> Dict:
        avg_delay = self.total_delay / self.total_departed if self.total_departed else 0
        throughput = self.total_departed / self.time * 3600 if self.time else 0
        jain = (sum(self.fairness_samples) / len(self.fairness_samples)
                if self.fairness_samples else 1.0)
        co2 = self.idle_veh_seconds * (130.0 / 60.0) / 1000.0
        return {
            "avg_delay_s_per_veh":       round(avg_delay, 2),
            "throughput_vph":            round(throughput, 1),
            "jain_fairness_index":       round(jain, 4),
            "split_failures":            self.split_failures,
            "co2_proxy_kg":              round(co2, 2),
            "context_switch_count":      self.context_switches,
            "context_switch_overhead_s": round(self.context_switches * self.yellow_time, 1),
            "flush_events":              0,
            "total_departed":            self.total_departed,
            "simulation_time_s":         round(self.time, 1),
        }


# ---------------------------------------------------------------------------
# 2. Actuated Controller (NEMA sensor-based)
# ---------------------------------------------------------------------------

class ActuatedController:
    """
    Semi-actuated controller: extends green as long as vehicles are detected,
    up to max_green. Uses a 'gap-out' threshold: if no vehicle arrives within
    `gap_threshold` seconds, phase terminates early.
    This is the dominant real-world baseline.
    """

    def __init__(
        self,
        lanes: Dict[str, Lane],
        phases: List[Phase],
        gap_threshold: float = 3.0,   # seconds between vehicles to gap-out
        yellow_time: float = 3.0,
        control_interval: float = 1.0,
    ):
        self.lanes = lanes
        self.phases = phases
        self.gap_threshold = gap_threshold
        self.yellow_time = yellow_time
        self.control_interval = control_interval

        self.phase_idx = 0
        self.elapsed = 0.0
        self.gap_timer = 0.0
        self.in_yellow = False
        self.yellow_elapsed = 0.0
        self.time = 0.0

        self.total_delay = 0.0
        self.total_departed = 0
        self.total_arrivals = 0
        self.context_switches = 0
        self.split_failures = 0
        self.idle_veh_seconds = 0.0
        self.fairness_samples: List[float] = []

    @property
    def current_phase(self) -> Phase:
        return self.phases[self.phase_idx]

    def process_arrivals(self, arrivals: Dict[str, int]):
        for lid, n in arrivals.items():
            if lid in self.lanes:
                self.lanes[lid].arrival(n)
                self.total_arrivals += n

    def step(self, arrivals: Optional[Dict[str, int]] = None):
        dt = self.control_interval
        self.time += dt

        if arrivals:
            self.process_arrivals(arrivals)

        for lane in self.lanes.values():
            lane.tick(dt)
            self.total_delay += lane.queue * dt
            self.idle_veh_seconds += lane.queue * dt

        if self.in_yellow:
            self.yellow_elapsed += dt
            if self.yellow_elapsed >= self.yellow_time:
                self.in_yellow = False
                self.yellow_elapsed = 0.0
                self.phase_idx = (self.phase_idx + 1) % len(self.phases)
                self.elapsed = 0.0
                self.gap_timer = 0.0
            return

        # Serve current phase
        served_any = False
        for uid, _ in self.current_phase.movements:
            lane = self.lanes.get(uid)
            if lane and lane.queue > 0:
                cap = max(1, int(lane.saturation_flow / 3600.0 * dt))
                d = lane.departure(cap)
                self.total_departed += d
                if d > 0:
                    served_any = True

        self.elapsed += dt

        # Gap-out logic: if no vehicles detected, increment gap timer
        active_queue = any(
            self.lanes[uid].queue > 0
            for uid, _ in self.current_phase.movements
            if uid in self.lanes
        )
        if active_queue:
            self.gap_timer = 0.0
        else:
            self.gap_timer += dt

        cp = self.current_phase
        gap_out = self.gap_timer >= self.gap_threshold and self.elapsed >= cp.min_green
        max_out = self.elapsed >= cp.max_green

        if gap_out or max_out:
            for uid, _ in self.current_phase.movements:
                if self.lanes.get(uid) and self.lanes[uid].queue > 0:
                    self.split_failures += 1
            self.in_yellow = True
            self.yellow_elapsed = 0.0
            self.context_switches += 1

        delays = [l.head_wait_time for l in self.lanes.values() if l.queue > 0]
        if delays:
            n = len(delays)
            jain = (sum(delays) ** 2) / (n * sum(d ** 2 for d in delays))
            self.fairness_samples.append(jain)

    def get_metrics(self) -> Dict:
        avg_delay = self.total_delay / self.total_departed if self.total_departed else 0
        throughput = self.total_departed / self.time * 3600 if self.time else 0
        jain = (sum(self.fairness_samples) / len(self.fairness_samples)
                if self.fairness_samples else 1.0)
        co2 = self.idle_veh_seconds * (130.0 / 60.0) / 1000.0
        return {
            "avg_delay_s_per_veh":       round(avg_delay, 2),
            "throughput_vph":            round(throughput, 1),
            "jain_fairness_index":       round(jain, 4),
            "split_failures":            self.split_failures,
            "co2_proxy_kg":              round(co2, 2),
            "context_switch_count":      self.context_switches,
            "context_switch_overhead_s": round(self.context_switches * self.yellow_time, 1),
            "flush_events":              0,
            "total_departed":            self.total_departed,
            "simulation_time_s":         round(self.time, 1),
        }


# ---------------------------------------------------------------------------
# 3. Pure Max-Pressure (beta=0, no fairness)
# ---------------------------------------------------------------------------

class MaxPressureController:
    """
    Tassiulas & Ephremides (1992) Max-Pressure.
    Selects phase maximising: P_s = sum mu_ud * (q_u - q_d)
    No WFQ fairness term (beta=0). Proves throughput-optimality but
    can starve low-volume lanes — TLMOS fixes this.
    """

    def __init__(
        self,
        lanes: Dict[str, Lane],
        phases: List[Phase],
        yellow_time: float = 3.0,
        control_interval: float = 1.0,
    ):
        self.lanes = lanes
        self.phases = {p.phase_id: p for p in phases}
        self.yellow_time = yellow_time
        self.control_interval = control_interval
        self.current_phase = phases[0]
        self.in_yellow = False
        self.yellow_elapsed = 0.0
        self.time = 0.0

        self.total_delay = 0.0
        self.total_departed = 0
        self.total_arrivals = 0
        self.context_switches = 0
        self.split_failures = 0
        self.idle_veh_seconds = 0.0
        self.fairness_samples: List[float] = []

    def _pressure(self, phase: Phase) -> float:
        p = 0.0
        for uid, did in phase.movements:
            u = self.lanes.get(uid)
            d = self.lanes.get(did)
            if u:
                mu = u.saturation_flow / 3600.0
                p += mu * (u.queue - (d.queue if d else 0))
        return p

    def process_arrivals(self, arrivals: Dict[str, int]):
        for lid, n in arrivals.items():
            if lid in self.lanes:
                self.lanes[lid].arrival(n)
                self.total_arrivals += n

    def step(self, arrivals: Optional[Dict[str, int]] = None):
        dt = self.control_interval
        self.time += dt

        if arrivals:
            self.process_arrivals(arrivals)

        for lane in self.lanes.values():
            lane.tick(dt)
            self.total_delay += lane.queue * dt
            self.idle_veh_seconds += lane.queue * dt

        if self.in_yellow:
            self.yellow_elapsed += dt
            if self.yellow_elapsed >= self.yellow_time:
                self.in_yellow = False
                self.yellow_elapsed = 0.0
            return

        for uid, _ in self.current_phase.movements:
            lane = self.lanes.get(uid)
            if lane and lane.queue > 0:
                cap = max(1, int(lane.saturation_flow / 3600.0 * dt))
                d = lane.departure(cap)
                self.total_departed += d

        self.current_phase.elapsed += dt

        if self.current_phase.elapsed < self.current_phase.min_green:
            return

        best = max(self.phases.values(), key=self._pressure)
        if best.phase_id != self.current_phase.phase_id:
            for uid, _ in self.current_phase.movements:
                if self.lanes.get(uid) and self.lanes[uid].queue > 0:
                    self.split_failures += 1
            self.in_yellow = True
            self.yellow_elapsed = 0.0
            self.context_switches += 1
            self.current_phase.elapsed = 0.0
            self.current_phase = best

        delays = [l.head_wait_time for l in self.lanes.values() if l.queue > 0]
        if delays:
            n = len(delays)
            jain = (sum(delays) ** 2) / (n * sum(d ** 2 for d in delays))
            self.fairness_samples.append(jain)

    def get_metrics(self) -> Dict:
        avg_delay = self.total_delay / self.total_departed if self.total_departed else 0
        throughput = self.total_departed / self.time * 3600 if self.time else 0
        jain = (sum(self.fairness_samples) / len(self.fairness_samples)
                if self.fairness_samples else 1.0)
        co2 = self.idle_veh_seconds * (130.0 / 60.0) / 1000.0
        return {
            "avg_delay_s_per_veh":       round(avg_delay, 2),
            "throughput_vph":            round(throughput, 1),
            "jain_fairness_index":       round(jain, 4),
            "split_failures":            self.split_failures,
            "co2_proxy_kg":              round(co2, 2),
            "context_switch_count":      self.context_switches,
            "context_switch_overhead_s": round(self.context_switches * self.yellow_time, 1),
            "flush_events":              0,
            "total_departed":            self.total_departed,
            "simulation_time_s":         round(self.time, 1),
        }