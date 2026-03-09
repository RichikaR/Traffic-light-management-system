"""
TLMOS Hybrid Kernel: Max-Pressure + Weighted Fair Queuing Scheduler
====================================================================
Implements the modified pressure term:
    P_s(t) = alpha * sum_{(u,d) in s} mu_{u,d} * (q_u - q_d)
           + beta  * max_{u in s} WaitTime_u(t)

where:
  alpha  - throughput weight hyperparameter
  beta   - fairness/anti-starvation weight hyperparameter
  q_u    - queue length on upstream link u
  q_d    - queue length on downstream link d
  mu_ud  - saturation flow rate for movement (u,d)
  WaitTime_u(t) - head-of-queue waiting time on lane u

The scheduler also implements Wait-for Graph (WFG) cycle detection
to identify and resolve deadlock (gridlock) conditions.
"""

from __future__ import annotations
import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import deque, defaultdict


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Lane:
    """Represents a single approach lane at an intersection."""
    lane_id: str
    queue: int = 0                  # number of vehicles waiting
    head_wait_time: float = 0.0     # seconds the front vehicle has waited
    saturation_flow: float = 1800.0 # veh/hr (standard = 1800)
    downstream_lane_id: Optional[str] = None  # for WFG deadlock detection

    def arrival(self, n: int = 1):
        self.queue += n

    def departure(self, n: int = 1):
        departed = min(n, self.queue)
        self.queue = max(0, self.queue - n)
        if self.queue == 0:
            self.head_wait_time = 0.0
        return departed

    def tick(self, dt: float):
        """Advance time: increment head-of-queue wait if queue non-empty."""
        if self.queue > 0:
            self.head_wait_time += dt


@dataclass
class Phase:
    """
    A signal phase = a set of non-conflicting movements (lane pairs).
    Analogous to a CPU scheduling slice.
    """
    phase_id: str
    movements: List[Tuple[str, str]]  # list of (upstream_lane_id, downstream_lane_id)
    min_green: float = 5.0    # seconds  (like minimum quantum)
    max_green: float = 60.0   # seconds
    elapsed: float = 0.0      # how long current green has run


@dataclass
class IntersectionState:
    """Complete state snapshot — used for context-save/restore during flush."""
    current_phase_id: str
    phase_elapsed: float
    queue_snapshot: Dict[str, int]
    wait_snapshot: Dict[str, float]


# ---------------------------------------------------------------------------
# Deadlock / Wait-for Graph detector
# ---------------------------------------------------------------------------

class WaitForGraph:
    """
    Models intersection-level gridlock as a directed graph where:
      node  = a lane
      edge  = lane A is waiting for lane B to clear (B blocks A's downstream)

    A cycle in this graph == deadlock (gridlock).
    Uses iterative DFS for cycle detection (edge-chasing algorithm).
    """

    def __init__(self):
        self.edges: Dict[str, List[str]] = defaultdict(list)

    def update(self, lanes: Dict[str, Lane]):
        """Rebuild graph from current lane states."""
        self.edges.clear()
        for lid, lane in lanes.items():
            if lane.queue > 0 and lane.downstream_lane_id:
                ds = lane.downstream_lane_id
                if ds in lanes and lanes[ds].queue > 0:
                    self.edges[lid].append(ds)

    def detect_cycle(self) -> Optional[List[str]]:
        """
        Returns the cycle (list of lane_ids) if deadlock detected, else None.
        Iterative DFS — O(V+E).
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color = defaultdict(int)
        parent = {}

        def dfs(start) -> Optional[List[str]]:
            stack = [(start, iter(self.edges.get(start, [])))]
            color[start] = GRAY
            while stack:
                node, children = stack[-1]
                try:
                    child = next(children)
                    if color[child] == GRAY:
                        # reconstruct cycle
                        cycle = [child]
                        cur = node
                        while cur != child:
                            cycle.append(cur)
                            cur = parent.get(cur, child)
                        cycle.append(child)
                        return cycle[::-1]
                    elif color[child] == WHITE:
                        color[child] = GRAY
                        parent[child] = node
                        stack.append((child, iter(self.edges.get(child, []))))
                except StopIteration:
                    color[node] = BLACK
                    stack.pop()
            return None

        for node in list(self.edges.keys()):
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result
        return None


# ---------------------------------------------------------------------------
# Hybrid Kernel Scheduler
# ---------------------------------------------------------------------------

class HybridKernel:
    """
    The TLMOS Hybrid Kernel.

    Scheduling policy:
      1. Every `control_interval` seconds, compute modified pressure P_s(t)
         for each phase s.
      2. Select phase s* = argmax P_s(t).
      3. If current phase has not reached min_green, extend it.
      4. If WFG cycle detected → trigger Flush Phase on bottleneck lane.
      5. Log all metrics for post-hoc analysis.

    Parameters
    ----------
    alpha : float
        Weight on throughput (Max-Pressure term). Higher = more throughput-greedy.
    beta : float
        Weight on fairness (WFQ head-wait term). Higher = more starvation-resistant.
        beta > 0 guarantees bounded delay for all movements (proof in docs/).
    yellow_time : float
        Fixed inter-phase clearance (analogous to context-switch overhead).
    control_interval : float
        How often the kernel re-evaluates (seconds). Analogous to scheduler tick.
    """

    def __init__(
        self,
        lanes: Dict[str, Lane],
        phases: List[Phase],
        alpha: float = 0.7,
        beta: float = 0.3,
        yellow_time: float = 3.0,
        control_interval: float = 1.0,
    ):
        if not phases:
            raise ValueError("At least one phase required.")

        self.lanes = lanes
        self.phases = {p.phase_id: p for p in phases}
        self.alpha = alpha
        self.beta = beta
        self.yellow_time = yellow_time
        self.control_interval = control_interval

        self.current_phase: Phase = phases[0]
        self.in_yellow: bool = False
        self.yellow_elapsed: float = 0.0
        self.time: float = 0.0

        self.wfg = WaitForGraph()
        self._saved_state: Optional[IntersectionState] = None

        # --- Metric accumulators ---
        self.total_delay: float = 0.0       # veh·s
        self.total_departed: int = 0
        self.total_arrivals: int = 0
        self.context_switches: int = 0      # phase changes
        self.flush_events: int = 0
        self.split_failures: int = 0        # phases where queue didn't clear
        self.idle_veh_seconds: float = 0.0  # proxy for CO2 (idling = ~2x fuel)
        self.fairness_samples: List[float] = []  # per-lane delay samples for Jain

    # ------------------------------------------------------------------
    # Core pressure computation
    # ------------------------------------------------------------------

    def _pressure(self, phase: Phase) -> float:
        """
        Modified pressure for a phase:
          P_s = alpha * Σ μ_ud*(q_u - q_d) + beta * max(WaitTime_u)
        """
        mp_term = 0.0
        max_wait = 0.0

        for (uid, did) in phase.movements:
            u = self.lanes.get(uid)
            d = self.lanes.get(did)
            if u is None:
                continue
            q_u = u.queue
            q_d = d.queue if d else 0
            mu = u.saturation_flow / 3600.0  # convert veh/hr → veh/s
            mp_term += mu * (q_u - q_d)
            max_wait = max(max_wait, u.head_wait_time)

        return self.alpha * mp_term + self.beta * max_wait

    def _select_phase(self) -> Phase:
        """Returns phase with highest modified pressure (argmax P_s)."""
        best = max(self.phases.values(), key=lambda p: self._pressure(p))
        return best

    # ------------------------------------------------------------------
    # Flush Phase — deadlock resolution (analogous to OS victim abort)
    # ------------------------------------------------------------------

    def _save_context(self):
        self._saved_state = IntersectionState(
            current_phase_id=self.current_phase.phase_id,
            phase_elapsed=self.current_phase.elapsed,
            queue_snapshot={lid: l.queue for lid, l in self.lanes.items()},
            wait_snapshot={lid: l.head_wait_time for lid, l in self.lanes.items()},
        )

    def _flush_phase(self, cycle: List[str]):
        """
        Context-save current state, then force-green the bottleneck lane
        (the lane in the deadlock cycle with the smallest queue — 
         smallest capacity to absorb, so clearing it breaks the chain).
        """
        self._save_context()
        self.flush_events += 1

        # Find bottleneck: minimum queue in cycle
        bottleneck = min(cycle, key=lambda lid: self.lanes[lid].queue)

        # Find the phase that serves this lane
        for phase in self.phases.values():
            for (uid, _) in phase.movements:
                if uid == bottleneck:
                    self.current_phase = phase
                    self.current_phase.elapsed = 0.0
                    return

    # ------------------------------------------------------------------
    # Arrivals and departures
    # ------------------------------------------------------------------

    def process_arrivals(self, arrivals: Dict[str, int]):
        """Called each control interval with new vehicle counts per lane."""
        for lid, n in arrivals.items():
            if lid in self.lanes:
                self.lanes[lid].arrival(n)
                self.total_arrivals += n

    def _serve_current_phase(self) -> int:
        """
        Discharge vehicles on active phase lanes.
        Returns total vehicles departed this interval.
        """
        departed = 0
        for (uid, _) in self.current_phase.movements:
            lane = self.lanes.get(uid)
            if lane and lane.queue > 0:
                # vehicles served = min(queue, saturation_flow * interval)
                capacity = int(lane.saturation_flow / 3600.0 * self.control_interval)
                capacity = max(capacity, 1)
                d = lane.departure(capacity)
                departed += d
                self.total_departed += d
        return departed

    # ------------------------------------------------------------------
    # Main step function — call once per control_interval
    # ------------------------------------------------------------------

    def step(self, arrivals: Optional[Dict[str, int]] = None):
        """
        Advance simulation by one control_interval.
          1. Process arrivals
          2. Tick all lanes (accumulate wait times / delay)
          3. Serve current green phase
          4. Check deadlock via WFG
          5. Decide phase switch
        """
        dt = self.control_interval
        self.time += dt

        if arrivals:
            self.process_arrivals(arrivals)

        # --- Tick lanes: accumulate delay ---
        for lane in self.lanes.values():
            lane.tick(dt)
            self.total_delay += lane.queue * dt
            self.idle_veh_seconds += lane.queue * dt  # idling proxy

        # --- Yellow clearance period ---
        if self.in_yellow:
            self.yellow_elapsed += dt
            if self.yellow_elapsed >= self.yellow_time:
                self.in_yellow = False
                self.yellow_elapsed = 0.0
            return  # no service during yellow

        # --- Serve current phase ---
        served_lane_ids = [uid for uid, _ in self.current_phase.movements]
        prev_queues = {lid: self.lanes[lid].queue for lid in served_lane_ids if lid in self.lanes}
        self._serve_current_phase()
        self.current_phase.elapsed += dt

        # --- Split failure check: did any served lane fail to clear? ---
        for uid, _ in self.current_phase.movements:
            if self.lanes.get(uid) and self.lanes[uid].queue > 0:
                if self.current_phase.elapsed >= self.current_phase.max_green:
                    self.split_failures += 1

        # --- Deadlock detection ---
        self.wfg.update(self.lanes)
        cycle = self.wfg.detect_cycle()
        if cycle:
            self._flush_phase(cycle)
            return

        # --- Phase selection ---
        if self.current_phase.elapsed < self.current_phase.min_green:
            return  # respect minimum green (Non-Preemptible Kernel Thread)

        best_phase = self._select_phase()
        if best_phase.phase_id != self.current_phase.phase_id:
            # Context switch: enter yellow
            self.context_switches += 1
            self.in_yellow = True
            self.yellow_elapsed = 0.0
            self.current_phase.elapsed = 0.0
            self.current_phase = best_phase

        elif self.current_phase.elapsed >= self.current_phase.max_green:
            # Force switch at max green (prevent starvation of other phases)
            all_phases = list(self.phases.values())
            idx = all_phases.index(self.current_phase)
            next_phase = all_phases[(idx + 1) % len(all_phases)]
            self.context_switches += 1
            self.in_yellow = True
            self.current_phase.elapsed = 0.0
            self.current_phase = next_phase

        # --- Sample fairness ---
        delays = [l.head_wait_time for l in self.lanes.values() if l.queue > 0]
        if delays:
            n = len(delays)
            jain = (sum(delays) ** 2) / (n * sum(d ** 2 for d in delays))
            self.fairness_samples.append(jain)

    # ------------------------------------------------------------------
    # Metrics summary
    # ------------------------------------------------------------------

    def get_metrics(self) -> Dict:
        avg_delay = (self.total_delay / self.total_departed
                     if self.total_departed > 0 else 0.0)
        throughput_vph = (self.total_departed / self.time * 3600
                          if self.time > 0 else 0.0)
        # Jain's Fairness Index (1.0 = perfect fairness)
        jain_index = (sum(self.fairness_samples) / len(self.fairness_samples)
                      if self.fairness_samples else 1.0)
        # CO2 proxy: idling vehicles emit ~130g CO2/min → convert
        co2_kg = self.idle_veh_seconds * (130.0 / 60.0) / 1000.0
        # Context switch overhead (lost time in yellow)
        cs_overhead_s = self.context_switches * self.yellow_time

        return {
            "avg_delay_s_per_veh":   round(avg_delay, 2),
            "throughput_vph":        round(throughput_vph, 1),
            "jain_fairness_index":   round(jain_index, 4),
            "split_failures":        self.split_failures,
            "co2_proxy_kg":          round(co2_kg, 2),
            "context_switch_count":  self.context_switches,
            "context_switch_overhead_s": round(cs_overhead_s, 1),
            "flush_events":          self.flush_events,
            "total_departed":        self.total_departed,
            "simulation_time_s":     round(self.time, 1),
        }