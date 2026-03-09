"""
Synthetic SUMO Network Generator
==================================
Creates a simple 4-way intersection .net.xml WITHOUT needing OSM or netconvert.
Use this to test the TraCI bridge immediately after installing SUMO,
before you generate the real Chennai network.

Usage:
    python sumo_integration/network/build_synthetic_network.py

Outputs:
    sumo_integration/network/synthetic_4way.net.xml
    sumo_integration/network/synthetic_4way.rou.xml
    sumo_integration/network/synthetic_4way.sumocfg
"""

import os
import xml.etree.ElementTree as ET

OUT_DIR = os.path.dirname(__file__)

NET_XML = """<?xml version="1.0" encoding="UTF-8"?>
<net version="1.16" junctionCornerDetail="5" limitTurnSpeed="5.50">

    <edge id=":J0_0" function="internal">
        <lane id=":J0_0_0" index="0" speed="13.89" length="9.0" shape="0.0,4.8 0.0,-4.8"/>
    </edge>
    <edge id=":J0_1" function="internal">
        <lane id=":J0_1_0" index="0" speed="13.89" length="9.0" shape="-4.8,0.0 4.8,0.0"/>
    </edge>

    <edge id="N2J" from="N" to="J0" priority="1">
        <lane id="N2J_0" index="0" speed="13.89" length="100.0" shape="1.6,100.0 1.6,4.8"/>
    </edge>
    <edge id="J2N" from="J0" to="N" priority="1">
        <lane id="J2N_0" index="0" speed="13.89" length="100.0" shape="-1.6,4.8 -1.6,100.0"/>
    </edge>
    <edge id="S2J" from="S" to="J0" priority="1">
        <lane id="S2J_0" index="0" speed="13.89" length="100.0" shape="-1.6,-100.0 -1.6,-4.8"/>
    </edge>
    <edge id="J2S" from="J0" to="S" priority="1">
        <lane id="J2S_0" index="0" speed="13.89" length="100.0" shape="1.6,-4.8 1.6,-100.0"/>
    </edge>
    <edge id="E2J" from="E" to="J0" priority="1">
        <lane id="E2J_0" index="0" speed="13.89" length="100.0" shape="100.0,-1.6 4.8,-1.6"/>
    </edge>
    <edge id="J2E" from="J0" to="E" priority="1">
        <lane id="J2E_0" index="0" speed="13.89" length="100.0" shape="4.8,1.6 100.0,1.6"/>
    </edge>
    <edge id="W2J" from="W" to="J0" priority="1">
        <lane id="W2J_0" index="0" speed="13.89" length="100.0" shape="-100.0,1.6 -4.8,1.6"/>
    </edge>
    <edge id="J2W" from="J0" to="W" priority="1">
        <lane id="J2W_0" index="0" speed="13.89" length="100.0" shape="-4.8,-1.6 -100.0,-1.6"/>
    </edge>

    <junction id="J0" type="traffic_light" x="0.0" y="0.0"
              incLanes="N2J_0 S2J_0 E2J_0 W2J_0"
              intLanes=":J0_0_0 :J0_1_0" shape="-4.8,4.8 4.8,4.8 4.8,-4.8 -4.8,-4.8">
        <request index="0" response="0010" foes="0110" cont="0"/>
        <request index="1" response="0001" foes="1001" cont="0"/>
        <request index="2" response="1000" foes="1100" cont="0"/>
        <request index="3" response="0100" foes="0110" cont="0"/>
    </junction>
    <junction id="N" type="dead_end" x="0.0" y="100.0" incLanes="J2N_0" intLanes=""/>
    <junction id="S" type="dead_end" x="0.0" y="-100.0" incLanes="J2S_0" intLanes=""/>
    <junction id="E" type="dead_end" x="100.0" y="0.0" incLanes="J2E_0" intLanes=""/>
    <junction id="W" type="dead_end" x="-100.0" y="0.0" incLanes="J2W_0" intLanes=""/>

    <tlLogic id="J0" type="static" programID="0" offset="0">
        <phase duration="35" state="GGrr" minDur="7" maxDur="55"/>
        <phase duration="3"  state="yyrr"/>
        <phase duration="35" state="rrGG" minDur="7" maxDur="55"/>
        <phase duration="3"  state="rryy"/>
    </tlLogic>

    <connection from="N2J" to="J2S" fromLane="0" toLane="0" via=":J0_0_0" tl="J0" linkIndex="0" dir="s" state="o"/>
    <connection from="S2J" to="J2N" fromLane="0" toLane="0" via=":J0_0_0" tl="J0" linkIndex="1" dir="s" state="o"/>
    <connection from="E2J" to="J2W" fromLane="0" toLane="0" via=":J0_1_0" tl="J0" linkIndex="2" dir="s" state="o"/>
    <connection from="W2J" to="J2E" fromLane="0" toLane="0" via=":J0_1_0" tl="J0" linkIndex="3" dir="s" state="o"/>
</net>
"""

ROU_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<routes>
    <vType id="car" accel="2.6" decel="4.5" sigma="0.5" length="4.5" maxSpeed="13.9"/>
    <vType id="motorcycle" accel="3.0" decel="4.0" sigma="0.5" length="2.0" maxSpeed="16.7"/>

    <!-- North-South through traffic (high volume = arterial) -->
    {ns_vehicles}

    <!-- East-West through traffic (lower volume = side street) -->
    {ew_vehicles}
</routes>
"""

CFG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <input>
        <net-file value="synthetic_4way.net.xml"/>
        <route-files value="synthetic_4way.rou.xml"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="3600"/>
        <step-length value="1.0"/>
    </time>
    <report>
        <no-warnings value="true"/>
        <no-step-log value="true"/>
    </report>
    <output>
        <tripinfo-output value="synthetic_tripinfo.xml"/>
    </output>
</configuration>
"""


def generate_vehicles(edge_from: str, edge_to: str, vtype: str,
                       count: int, start: int = 0, interval: float = 3.0) -> str:
    lines = []
    for i in range(count):
        depart = start + i * interval
        lines.append(
            f'    <vehicle id="{edge_from}_{i}" type="{vtype}" '
            f'depart="{depart:.1f}">'
            f'<route edges="{edge_from} {edge_to}"/></vehicle>'
        )
    return "\n".join(lines)


def build_synthetic_network(scenario: str = "moderate"):
    """
    scenario: "moderate" (~600 vph N-S, ~200 vph E-W)
              "saturated" (~1200 vph N-S, ~400 vph E-W)
              "asymmetric" (~1000 vph N-S, ~100 vph E-W)
    """
    params = {
        "moderate":   {"ns_vph": 600,  "ew_vph": 200},
        "saturated":  {"ns_vph": 1200, "ew_vph": 400},
        "asymmetric": {"ns_vph": 1000, "ew_vph": 100},
    }
    p = params.get(scenario, params["moderate"])

    # Vehicles per direction over 3600s
    ns_interval = 3600.0 / p["ns_vph"] if p["ns_vph"] > 0 else 9999
    ew_interval = 3600.0 / p["ew_vph"] if p["ew_vph"] > 0 else 9999

    ns_vehs = (
        generate_vehicles("N2J", "J2S", "car",        int(p["ns_vph"]*0.4), interval=ns_interval) + "\n" +
        generate_vehicles("S2J", "J2N", "car",        int(p["ns_vph"]*0.4), interval=ns_interval) + "\n" +
        generate_vehicles("N2J", "J2S", "motorcycle", int(p["ns_vph"]*0.2), interval=ns_interval)
    )
    ew_vehs = (
        generate_vehicles("E2J", "J2W", "car",        int(p["ew_vph"]*0.4), interval=ew_interval) + "\n" +
        generate_vehicles("W2J", "J2E", "car",        int(p["ew_vph"]*0.4), interval=ew_interval) + "\n" +
        generate_vehicles("E2J", "J2W", "motorcycle", int(p["ew_vph"]*0.2), interval=ew_interval)
    )

    rou_xml = ROU_XML_TEMPLATE.format(ns_vehicles=ns_vehs, ew_vehicles=ew_vehs)

    net_path = os.path.join(OUT_DIR, "synthetic_4way.net.xml")
    rou_path = os.path.join(OUT_DIR, f"synthetic_4way_{scenario}.rou.xml")
    cfg_path = os.path.join(OUT_DIR, f"synthetic_{scenario}.sumocfg")

    with open(net_path, "w") as f:
        f.write(NET_XML)
    with open(rou_path, "w") as f:
        f.write(rou_xml)

    cfg = CFG_XML.replace("synthetic_4way.rou.xml",
                          f"synthetic_4way_{scenario}.rou.xml")
    cfg = cfg.replace("synthetic_tripinfo.xml",
                      f"synthetic_tripinfo_{scenario}.xml")
    with open(cfg_path, "w") as f:
        f.write(cfg)

    print(f"✓ Synthetic {scenario} network:")
    print(f"  Net    : {net_path}")
    print(f"  Routes : {rou_path}")
    print(f"  Config : {cfg_path}")
    print(f"\n  N-S demand: {p['ns_vph']} veh/hr  |  E-W demand: {p['ew_vph']} veh/hr")
    print(f"\nTest with:")
    print(f"  python sumo_integration/traci_bridge/run_sumo_benchmark.py "
          f"--config {cfg_path} --scenario {scenario}")
    return cfg_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="all",
                        choices=["moderate", "saturated", "asymmetric", "all"])
    args = parser.parse_args()

    scenarios = ["moderate", "saturated", "asymmetric"] if args.scenario == "all" \
                else [args.scenario]
    for s in scenarios:
        print(f"\n▶ Building synthetic {s} network...")
        build_synthetic_network(s)