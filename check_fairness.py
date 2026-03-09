"""
Per-lane fairness diagnostic.
Runs MP vs TLMOS and prints per-lane wait times to show starvation difference.
"""
import sys, os
sys.path.insert(0, os.getcwd())
from simulation.kernel.hybrid_scheduler import HybridKernel, Lane, Phase
from simulation.baselines.controllers import MaxPressureController
from simulation.scenarios.intersection import build_single_intersection, poisson_arrivals, ASYMMETRIC_DEMAND
import random, copy

random.seed(42)
duration = 3600

for name, cls, kwargs in [
    ("Max-Pressure", MaxPressureController, {"yellow_time": 3.0}),
    ("TLMOS",        HybridKernel,          {"alpha": 0.7, "beta": 0.3, "yellow_time": 3.0}),
]:
    lanes, phases = build_single_intersection()
    ctrl = cls(lanes=copy.deepcopy(lanes), phases=copy.deepcopy(phases), **kwargs)
    for t in range(duration):
        ctrl.step(poisson_arrivals(ASYMMETRIC_DEMAND))

    print(f"\n{'='*50}")
    print(f"  {name} — Per-lane head wait times (final)")
    print(f"{'='*50}")
    for lid, lane in ctrl.lanes.items():
        print(f"  {lid:<12} queue={lane.queue:>3}  head_wait={lane.head_wait_time:>8.1f}s")
    m = ctrl.get_metrics()
    print(f"\n  Jain Fairness Index : {m['jain_fairness_index']}")
    print(f"  Avg Delay           : {m['avg_delay_s_per_veh']}s")
