import os
import sys
import sumolib

# Ensure access to src for config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))
from src.config import SimConfig

class NetworkGraphProvider:
    def __init__(self):
        self.net_file = SimConfig.NET_FILE

    def get_graph_data(self):
        if not os.path.exists(self.net_file):
            return {"error": f"Network file not found: {self.net_file}", "nodes": [], "edges": []}
        
        try:
            net = sumolib.net.readNet(self.net_file)
            
            nodes = []
            for node in net.getNodes():
                x, y = node.getCoord()
                nodes.append({
                    "id": node.getID(),
                    "x": x,
                    "y": y,
                    "type": node.getType()
                })
                
            edges = []
            for edge in net.getEdges():
                edges.append({
                    "id": edge.getID(),
                    "from": edge.getFromNode().getID(),
                    "to": edge.getToNode().getID()
                })
                
            return {"nodes": nodes, "edges": edges}
        except Exception as e:
            return {"error": str(e), "nodes": [], "edges": []}
