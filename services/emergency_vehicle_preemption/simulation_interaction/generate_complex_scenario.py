import os
import random
import sumolib

# Configure paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(BASE_DIR, "../simulation/networks/complex_evaluation.net.xml")
ROU_FILE = os.path.join(BASE_DIR, "../simulation/routes/complex_evaluation.rou.xml")
SUMOCFG_FILE = os.path.join(BASE_DIR, "../simulation/config/complex_evaluation.sumocfg")

def generate_scenario():
    print(f"Reading network from {NET_FILE}...")
    net = sumolib.net.readNet(NET_FILE)
    edges = net.getEdges()
    valid_edges = [e.getID() for e in edges if e.allows("passenger")]
    
    # Identify fringe edges that connect to the outside world
    origins = [e.getID() for e in edges if e.allows("passenger") and len(e.getFromNode().getIncoming()) == 0]
    destinations = [e.getID() for e in edges if e.allows("passenger") and len(e.getToNode().getOutgoing()) == 0]
    
    # Fallback to valid edges if map lacks fringes
    if not origins: origins = valid_edges
    if not destinations: destinations = valid_edges
    
    with open(ROU_FILE, "w") as routes:
        routes.write('<routes>\n')
        routes.write('    <vType id="car" maxSpeed="20.0" vClass="passenger"/>\n')
        routes.write('    <vType id="ambulance" maxSpeed="30.0" vClass="emergency" color="red" guiShape="emergency" speedFactor="1.5">\n')
        routes.write('        <param key="has.bluelight.device" value="true"/>\n')
        routes.write('    </vType>\n\n')

        veh_id = 0
        
        # Helper to pick random valid edges
        def get_od():
            return random.choice(origins), random.choice(destinations)
        
        # Phase 1: Low Traffic (0 - 1500)
        print("Generating Phase 1: Low Traffic (0-1500s)...")
        for step in range(0, 1500):
            if step % 5 == 0:  # 1 car every 5 seconds
                origin, dest = get_od()
                if origin != dest:
                    routes.write(f'    <trip id="flow_{veh_id}" type="car" depart="{step}" from="{origin}" to="{dest}"/>\n')
                    veh_id += 1
            
            # EVs in Phase 1 (Spread out)
            if step in [500, 1000]:
                origin, dest = get_od()
                if origin != dest:
                    routes.write(f'    <trip id="EV_Phase1_{step}" type="ambulance" depart="{step}" from="{origin}" to="{dest}"/>\n')
        
        # Phase 2: Medium Traffic (1500 - 3000)
        print("Generating Phase 2: Medium Traffic (1500-3000s)...")
        for step in range(1500, 3000):
            if step % 2 == 0:  # 1 car every 2 seconds
                origin, dest = get_od()
                if origin != dest:
                    routes.write(f'    <trip id="flow_{veh_id}" type="car" depart="{step}" from="{origin}" to="{dest}"/>\n')
                    veh_id += 1
            
            # EVs in Phase 2
            if step % 300 == 0:
                origin, dest = get_od()
                if origin != dest:
                    routes.write(f'    <trip id="EV_Phase2_{step}" type="ambulance" depart="{step}" from="{origin}" to="{dest}"/>\n')

        # Phase 3: High Traffic (3000 - 4500)
        print("Generating Phase 3: High Traffic (3000-4500s)...")
        for step in range(3000, 4500):
            # 2 cars per second
            for _ in range(2):
                origin, dest = get_od()
                if origin != dest:
                    routes.write(f'    <trip id="flow_{veh_id}" type="car" depart="{step}" from="{origin}" to="{dest}"/>\n')
                    veh_id += 1
            
            # High concurrency EVs in Phase 3
            if 3500 <= step <= 3600 and step % 10 == 0:
                origin, dest = get_od()
                if origin != dest:
                    routes.write(f'    <trip id="EV_Phase3_{step}" type="ambulance" depart="{step}" from="{origin}" to="{dest}"/>\n')

        routes.write('</routes>\n')

    # Generate SUMOCFG
    print(f"Generating SUMOCFG file at {SUMOCFG_FILE}...")
    with open(SUMOCFG_FILE, "w") as cfg:
        cfg.write('<configuration>\n')
        cfg.write('    <input>\n')
        cfg.write('        <net-file value="../networks/complex_evaluation.net.xml"/>\n')
        cfg.write('        <route-files value="../routes/complex_evaluation.rou.xml"/>\n')
        cfg.write('    </input>\n')
        cfg.write('    <time>\n')
        cfg.write('        <begin value="0"/>\n')
        cfg.write('        <end value="4500"/>\n')
        cfg.write('    </time>\n')
        cfg.write('</configuration>\n')
        
    print(f"Successfully generated scenario. Total civil vehicles: {veh_id}. Total EVs generated.")

if __name__ == "__main__":
    generate_scenario()
