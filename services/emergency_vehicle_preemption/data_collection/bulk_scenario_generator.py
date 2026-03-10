import os
import random
import sumolib

# Configure paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NET_FILE = os.path.join(BASE_DIR, "../simulation/networks/complex_evaluation.net.xml")
ROUTES_DIR = os.path.join(BASE_DIR, "../simulation/routes/bulk_scenarios")
CONFIGS_DIR = os.path.join(BASE_DIR, "../simulation/config/bulk_scenarios")

os.makedirs(ROUTES_DIR, exist_ok=True)
os.makedirs(CONFIGS_DIR, exist_ok=True)

NUM_SCENARIOS = 50  # Generate 50 different traffic profiles
SIM_DURATION = 4000 # 4000 seconds per scenario

def generate_bulk_scenarios():
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
    
    if not valid_edges:
        print("ERROR: No valid passenger edges found in the network.")
        return

    print(f"Generating {NUM_SCENARIOS} randomized scenarios...")

    for i in range(NUM_SCENARIOS):
        rou_filename = f"scenario_{i}.rou.xml"
        cfg_filename = f"scenario_{i}.sumocfg"
        
        rou_filepath = os.path.join(ROUTES_DIR, rou_filename)
        cfg_filepath = os.path.join(CONFIGS_DIR, cfg_filename)

        with open(rou_filepath, "w") as routes:
            routes.write('<routes>\n')
            routes.write('    <vType id="car" maxSpeed="20.0" vClass="passenger"/>\n')
            routes.write('    <vType id="ambulance" maxSpeed="30.0" vClass="emergency" color="red" guiShape="emergency" speedFactor="1.5">\n')
            routes.write('        <param key="has.bluelight.device" value="true"/>\n')
            routes.write('    </vType>\n\n')

            veh_id = 0
            ev_id = 0
            
            def get_od():
                return random.choice(origins), random.choice(destinations)

            # Randomize traffic profiles for this specific scenario
            # Base density per 10 seconds. Sparse = 1, Gridlock = 30
            base_traffic_density = random.randint(1, 30) 
            ev_spawn_rate = random.randint(50, 400) # Spawn an EV every 50 to 400 seconds
            
            for step in range(0, SIM_DURATION):
                # Spawn civilian traffic
                # Higher base_traffic_density means more cars spawned each step probabilistically
                spawn_prob = base_traffic_density / 10.0
                while spawn_prob > 1.0:
                    spawn_prob -= 1.0
                    origin, dest = get_od()
                    if origin != dest:
                        routes.write(f'    <trip id="car_{i}_{veh_id}" type="car" depart="{step}" from="{origin}" to="{dest}"/>\n')
                        veh_id += 1

                if random.random() < spawn_prob:
                    origin, dest = get_od()
                    if origin != dest:
                        routes.write(f'    <trip id="car_{i}_{veh_id}" type="car" depart="{step}" from="{origin}" to="{dest}"/>\n')
                        veh_id += 1
                
                # Spawn Emergency Vehicles
                if step % ev_spawn_rate == 0:
                    origin, dest = get_od()
                    if origin != dest:
                        routes.write(f'    <trip id="EV_{i}_{ev_id}" type="ambulance" depart="{step}" from="{origin}" to="{dest}"/>\n')
                        ev_id += 1

            routes.write('</routes>\n')

        # Generate SUMOCFG for this scenario
        # Calculate relative paths properly from CONFIGS_DIR to NET_FILE and ROUTES_DIR
        rel_net_filepath = os.path.relpath(NET_FILE, CONFIGS_DIR)
        rel_rou_filepath = os.path.relpath(rou_filepath, CONFIGS_DIR)

        with open(cfg_filepath, "w") as cfg:
            cfg.write('<configuration>\n')
            cfg.write('    <input>\n')
            cfg.write(f'        <net-file value="{rel_net_filepath}"/>\n')
            cfg.write(f'        <route-files value="{rel_rou_filepath}"/>\n')
            cfg.write('    </input>\n')
            cfg.write('    <time>\n')
            cfg.write('        <begin value="0"/>\n')
            cfg.write(f'        <end value="{SIM_DURATION}"/>\n')
            cfg.write('    </time>\n')
            cfg.write('</configuration>\n')
            
    print(f"Successfully generated {NUM_SCENARIOS} diverse scenario configurations in {CONFIGS_DIR}.")

if __name__ == "__main__":
    generate_bulk_scenarios()
