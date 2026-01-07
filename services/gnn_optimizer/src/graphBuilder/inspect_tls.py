import sumolib
import os

# Use the path from the error log
net_file = r"C:\projects\research\services\emergency_vehicle_preemption\simulation\networks\katunayake.net.xml"

if not os.path.exists(net_file):
    print(f"File not found: {net_file}")
    # Fallback to a simpler check if file doesn't exist (though it should based on logs)
    exit(1)

try:
    net = sumolib.net.readNet(net_file)
    tls_list = net.getTrafficLights()
    
    if not tls_list:
        print("No traffic lights found in the network.")
    else:
        tls = tls_list[0]
        print(f"Inspecting TLS: {tls.getID()}")
        print("Attributes/Methods:")
        for attr in dir(tls):
            if not attr.startswith("__"):
                print(f" - {attr}")
                
        # Try to find how to get nodes
        print("\nTrying to find nodes...")
        # Check connections
        connections = tls.getConnections()
        print(f"Number of connections: {len(connections)}")
        if connections:
            c = connections[0]
            print(f"Sample connection: {c}")
            # A connection is usually [fromEdge, toEdge, fromLane, toLane] (list) or similar
            
except Exception as e:
    print(f"Error: {e}")
