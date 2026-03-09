import sumolib
import os
import random

def generate_demand(net_file, out_file):
    print(f"Reading network from {net_file}...")
    net = sumolib.net.readNet(net_file)
    
    sources = []
    sinks = []
    
    for edge in net.getEdges():
        if edge.getFunction() == 'internal':
            continue
            
        has_incoming = len(edge.getIncoming()) > 0
        has_outgoing = len(edge.getOutgoing()) > 0
        
        # Check if the edge allows passenger or emergency vehicles
        allowed = False
        for lane in edge.getLanes():
            if lane.allows("passenger") or lane.allows("emergency"):
                allowed = True
                break
                
        if not allowed:
            continue
            
        if not has_incoming:
            sources.append(edge)
            
        if not has_outgoing:
            sinks.append(edge)
            
    print(f"Found {len(sources)} pure source edges and {len(sinks)} pure sink edges.")
    
    if len(sources) == 0 or len(sinks) == 0:
        print("Warning: Insufficient pure sources or sinks. Adding pseudo-fringe edges...")
        if len(sources) == 0:
            sources = [e for e in net.getEdges() if e.getFunction() != 'internal']
        if len(sinks) == 0:
            sinks = [e for e in net.getEdges() if e.getFunction() != 'internal']

    time_steps = 3600
    num_background = 1000
    num_ev = 20

    trips = []
    
    # Generate background trips
    for i in range(num_background):
        depart = random.uniform(0, time_steps)
        src = random.choice(sources)
        dst = random.choice(sinks)
        
        # Ensure source and destination are different
        attempts = 0
        while src == dst and attempts < 10:
            dst = random.choice(sinks)
            attempts += 1
            
        trips.append(('car', f'flow_{i}', depart, src.getID(), dst.getID()))

    # Generate EVs
    for i in range(1, num_ev + 1):
        depart = random.uniform(0, time_steps)
        src = random.choice(sources)
        dst = random.choice(sinks)
        
        attempts = 0
        while src == dst and attempts < 10:
            dst = random.choice(sinks)
            attempts += 1
            
        trips.append(('ambulance', f'EV_{i}', depart, src.getID(), dst.getID()))

    # Sort by departure time
    trips.sort(key=lambda x: x[2])

    print(f"Writing {len(trips)} trips to {out_file}...")
    with open(out_file, 'w') as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<routes xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/routes_file.xsd">\n')
        
        f.write('    <!-- Vehicle Types -->\n')
        f.write('    <vType id="car" vClass="passenger" guiShape="passenger" length="5.0" maxSpeed="15.0" accel="2.6" decel="4.5"/>\n')
        f.write('    <vType id="ambulance" vClass="emergency" guiShape="emergency" speedFactor="1.5"/>\n\n')
        
        for t in trips:
            vtype, vid, depart, src, dst = t
            f.write(f'    <trip id="{vid}" type="{vtype}" depart="{depart:.2f}" from="{src}" to="{dst}" />\n')
            
        f.write('</routes>\n')

if __name__ == '__main__':
    base_dir = r"f:\Repositories\temp\research-temp-3\multi-agent-urban-traffic-signal-optimization-in-simulated-environments\simulation_and_control_panel\scenarios\Katunayake"
    net_file = os.path.join(base_dir, "katunayake.net.xml")
    out_file = os.path.join(base_dir, "katunayake.rou.xml")
    
    random.seed(42)
    generate_demand(net_file, out_file)
