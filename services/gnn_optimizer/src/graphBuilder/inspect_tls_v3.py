import sumolib
import os

net_file = r"C:\projects\research\services\emergency_vehicle_preemption\simulation\networks\katunayake.net.xml"

try:
    net = sumolib.net.readNet(net_file)
    
    print("\n--- Inspecting TLS Connections ---")
    tls_list = net.getTrafficLights()
    if tls_list:
        tls = tls_list[0]
        conns = tls.getConnections()
        print(f"TLS ID: {tls.getID()}")
        print(f"getConnections() type: {type(conns)}")
        print(f"getConnections() len: {len(conns)}")
        
        if len(conns) > 0:
            first_item = conns[0]
            print(f"Item 0 type: {type(first_item)}")
            print(f"Item 0: {first_item}")
            
            # If it's a list, inspect elements
            if isinstance(first_item, list):
                if len(first_item) > 0:
                    sub_item = first_item[0]
                    print(f"Sub Item 0 type: {type(sub_item)}")
                    print(f"Sub Item 0 dir: {dir(sub_item)}")
                    
                    # Check if it's a Lane
                    if hasattr(sub_item, "getEdge"):
                        print("It is a Lane object.")
                        edge = sub_item.getEdge()
                        print(f"Edge ID: {edge.getID()}")
                        print(f"To Node: {edge.getToNode().getID()}")

    print("\n--- Inspecting Lane Outgoing Connections ---")
    # Find a lane that goes into a TLS
    for edge in net.getEdges():
        to_node = edge.getToNode()
        if to_node.getType() == "traffic_light":
            lane = edge.getLanes()[0]
            outgoing = lane.getOutgoing()
            if outgoing:
                conn = outgoing[0]
                print(f"Connection from {lane.getID()} to {conn.getToLane().getID()}")
                print(f"Connection dir: {dir(conn)}")
                if hasattr(conn, "getTLSID"):
                    print(f"TLS ID: {conn.getTLSID()}")
                break

except Exception as e:
    print(f"Error: {e}")
