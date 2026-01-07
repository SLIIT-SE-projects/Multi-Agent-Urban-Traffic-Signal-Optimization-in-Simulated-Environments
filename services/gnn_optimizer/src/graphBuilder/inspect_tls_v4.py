import sumolib
import os

net_file = r"C:\projects\research\services\emergency_vehicle_preemption\simulation\networks\katunayake.net.xml"

try:
    net = sumolib.net.readNet(net_file)
    tls_list = net.getTrafficLights()
    
    if tls_list:
        tls = tls_list[0]
        conns = tls.getConnections()
        print(f"TLS ID: {tls.getID()}")
        print(f"Number of connections: {len(conns)}")
        
        for i, c in enumerate(conns):
            print(f"Connection {i}: {c}")
            print(f"Type: {type(c)}")
            if isinstance(c, list) or isinstance(c, tuple):
                print(f"Length: {len(c)}")
                for j, item in enumerate(c):
                    print(f"  Item {j} type: {type(item)}")
                    if hasattr(item, "getID"):
                        print(f"  Item {j} ID: {item.getID()}")
            
            # Check if we can assume index 0 is always the lane
            if len(c) > 0 and isinstance(c[0], sumolib.net.lane.Lane):
                print("  -> Index 0 is Lane")
            else:
                print("  -> Index 0 is NOT Lane")
            
            if i >= 2: break # Just check first few

except Exception as e:
    print(f"Error: {e}")
