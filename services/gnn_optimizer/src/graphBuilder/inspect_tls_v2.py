import sumolib
import os

net_file = r"C:\projects\research\services\emergency_vehicle_preemption\simulation\networks\katunayake.net.xml"

try:
    net = sumolib.net.readNet(net_file)
    
    print("--- Inspecting Nodes ---")
    tls_nodes = [n for n in net.getNodes() if n.getType() == "traffic_light"]
    if tls_nodes:
        node = tls_nodes[0]
        print(f"Node ID: {node.getID()}")
        print("Node Attributes:")
        for attr in dir(node):
            if "tls" in attr.lower() or "traffic" in attr.lower():
                print(f" - {attr}")
        
        # Check if we can get TLS ID from node
        # Usually node doesn't store TLS ID directly in sumolib, but let's check.
    
    print("\n--- Inspecting TLS ---")
    tls_list = net.getTrafficLights()
    if tls_list:
        tls = tls_list[0]
        print(f"TLS ID: {tls.getID()}")
        print("TLS Attributes:")
        for attr in dir(tls):
             if not attr.startswith("__"):
                print(f" - {attr}")
        
        print("\nChecking getConnections():")
        if hasattr(tls, "getConnections"):
            conns = tls.getConnections()
            print(f"Count: {len(conns)}")
            if conns:
                # conns is usually a list of lists of Connections? or just Connections?
                # Let's inspect the first element
                c = conns[0]
                print(f"First Connection: {c}")
                # If it's a list (phases?), we might need to dig deeper
                if isinstance(c, list):
                     print(f"First element is list, len: {len(c)}")
                     if len(c) > 0:
                         print(f"Inner: {c[0]}")
                         print(f"Inner type: {type(c[0])}")
                         print(f"Inner dir: {dir(c[0])}")

except Exception as e:
    print(f"Error: {e}")
