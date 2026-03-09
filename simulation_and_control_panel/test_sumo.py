import os, sys
import traci

if 'SUMO_HOME' in os.environ:
    tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
    sys.path.append(tools)
else:
    sys.exit("Please declare environment variable 'SUMO_HOME'")

sumocfg = r"f:/Repositories/temp/research-temp-3/multi-agent-urban-traffic-signal-optimization-in-simulated-environments/simulation_and_control_panel/scenarios/Katunayake/katunayake.sumocfg"

traci.start(["sumo", "-c", sumocfg, "--scale", "0"]) # Suppress demand to mirror issue
print("Routes:", list(traci.route.getIDList()))
print("Vehicles:", list(traci.vehicle.getIDList()))
traci.close()
