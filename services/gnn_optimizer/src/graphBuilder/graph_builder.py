import torch
from torch_geometric.data import HeteroData
import sumolib
import numpy as np
from src.config import GraphConfig
from collections import defaultdict

class TrafficGraphBuilder:
    def __init__(self, net_file_path):
        
        print(f"Loading Network: {net_file_path}")
        # withNodeNeighbors=True ensures we can traverse the graph topology
        self.net = sumolib.net.readNet(net_file_path, withNodeNeighbors=True)
        
        # --- 1. Identify Nodes (Intersections & Lanes) ---
        
        # FIX: Iterate over Traffic Lights, not just Nodes
        self.tls_objects = self.net.getTrafficLights()
        
        # FIX: Get all lanes by iterating through all edges first
        self.all_lanes = []
        for edge in self.net.getEdges():
            # Filter out internal function lanes (usually start with ':')
            # if edge.getFunction() == 'internal': continue
            self.all_lanes.extend(edge.getLanes())

        # Create Mappings: String ID -> Integer Index
        self.tls_map = {tls.getID(): i for i, tls in enumerate(self.tls_objects)}
        self.lane_map = {lane.getID(): i for i, lane in enumerate(self.all_lanes)}
        
        # Map physical Nodes to their controlling TLS
        self.node_to_tls_id = {}
        self.tls_to_nodes = defaultdict(set) # New map: TLS ID -> Set of Nodes
        
        for tls in self.tls_objects:
            self.tls_to_nodes[tls.getID()] = set()
            # tls.getConnections() returns a list of lists: [IncomingLane, OutgoingLane, LinkIndex]
            conns = tls.getConnections()
            for conn_list in conns:
                if len(conn_list) > 0:
                    lane = conn_list[0] # The first element is the incoming lane
                    # The lane leads TO the intersection controlled by this TLS
                    node = lane.getEdge().getToNode()
                    self.node_to_tls_id[node.getID()] = tls.getID()
                    self.tls_to_nodes[tls.getID()].add(node)
        
        self.num_intersections = len(self.tls_objects)
        self.num_lanes = len(self.all_lanes)
        
        print(f"Graph Initialized: {self.num_intersections} Traffic Light Systems, {self.num_lanes} Lanes.")
        print(f"Graph Builder: Mapped {len(self.tls_map)} Traffic Light Systems")

        # --- 2. Build Static Edges ---
        self.static_edges = self._build_static_topology()

    def _build_static_topology(self):
        
        src_part_of, dst_part_of = [], []
        edge_attr_part_of = [] # [NEW] Store physical features
        
        src_adj, dst_adj = [], []
        src_feed, dst_feed = [], []

        # A. Lane -> Intersection Connectivity ('part_of')
        for lane in self.all_lanes:
            lane_id = lane.getID()
            edge = lane.getEdge()
            # The edge points TO a node. That node is the intersection this lane feeds.
            target_node = edge.getToNode()
            
            # Check if the target node is controlled by a TLS
            if target_node.getID() in self.node_to_tls_id:
                tls_id = self.node_to_tls_id[target_node.getID()]
                if tls_id in self.tls_map:
                    l_idx = self.lane_map[lane_id]
                    i_idx = self.tls_map[tls_id]
                    
                    src_part_of.append(l_idx)
                    dst_part_of.append(i_idx)
                    
                    # [NEW] Extract Physical Edge Features & Normalize
                    # Max expected road length ~1000m, max speed ~33m/s (120km/h)
                    norm_length = min(lane.getLength() / 1000.0, 1.0)
                    norm_speed_limit = min(lane.getSpeed() / 33.33, 1.0)
                    edge_attr_part_of.append([norm_length, norm_speed_limit])

        # B. Intersection -> Intersection Topology ('adjacent_to')
        for tls in self.tls_objects:
            u_idx = self.tls_map[tls.getID()]
            
            # A TLS might control multiple nodes. We need to check neighbors of ALL controlled nodes.
            visited_neighbors = set()
            
            # Use our pre-calculated nodes list
            if tls.getID() in self.tls_to_nodes:
                for node in self.tls_to_nodes[tls.getID()]:
                    for outgoing_edge in node.getOutgoing():
                        neighbor_node = outgoing_edge.getToNode()
                        
                        # If neighbor is controlled by a DIFFERENT TLS
                        if neighbor_node.getID() in self.node_to_tls_id:
                            neighbor_tls_id = self.node_to_tls_id[neighbor_node.getID()]
                            
                            if neighbor_tls_id != tls.getID() and neighbor_tls_id in self.tls_map:
                                if neighbor_tls_id not in visited_neighbors:
                                    v_idx = self.tls_map[neighbor_tls_id]
                                    src_adj.append(u_idx)
                                    dst_adj.append(v_idx)
                                    visited_neighbors.add(neighbor_tls_id)
        
        # C. Lane -> Lane Flow ('feeds_into')
        for lane in self.all_lanes:
            if lane.getID() not in self.lane_map: continue
            l_from_idx = self.lane_map[lane.getID()]
            
            # getOutgoing returns a list of Connection objects
            for conn in lane.getOutgoing():
                to_lane = conn.getToLane()
                if to_lane.getID() in self.lane_map:
                    l_to_idx = self.lane_map[to_lane.getID()]
                    src_feed.append(l_from_idx)
                    dst_feed.append(l_to_idx)

        return {
            'part_of': torch.tensor([src_part_of, dst_part_of], dtype=torch.long),
            'part_of_attr': torch.tensor(edge_attr_part_of, dtype=torch.float), # [NEW] Added tensor
            'adjacent': torch.tensor([src_adj, dst_adj], dtype=torch.long),
            'feeds': torch.tensor([src_feed, dst_feed], dtype=torch.long)
        }

    def _get_lane_features(self, lane_id, snapshot):
        lane_data = snapshot['lanes'][lane_id]
        
        MAX_CAPACITY = 50.0 
        MAX_SPEED = 13.89
        
        norm_queue = min(lane_data['queue_length'] / MAX_CAPACITY, 1.0)
        
        norm_wait = min(lane_data['total_wait_time'] / 120.0, 1.0)
        
        norm_avg_speed = min(lane_data['avg_speed'] / MAX_SPEED, 1.0)
        
        return [norm_queue, norm_wait, norm_avg_speed]

    def create_hetero_data(self, snapshot):
        
        data = HeteroData()
        
        # 1. Node Features (Dynamic)
        
        # A. Intersection Features & Positions
        x_inter = torch.zeros((self.num_intersections, GraphConfig.INTERSECTION_INPUT_DIM), dtype=torch.float)
        pos_inter = [[0.0, 0.0] for _ in range(self.num_intersections)]
        
        for tls_id, info in snapshot['intersections'].items():
            if tls_id in self.tls_map:
                idx = self.tls_map[tls_id]
                # Features
                p_idx = int(info['phase_index']) % GraphConfig.NUM_SIGNAL_PHASES
                x_inter[idx, p_idx] = 1.0 
                x_inter[idx, GraphConfig.NUM_SIGNAL_PHASES] = float(info['time_to_switch'])
                
                # Position: Average of all controlled nodes
                try:
                    if tls_id in self.tls_to_nodes and self.tls_to_nodes[tls_id]:
                        nodes = list(self.tls_to_nodes[tls_id])
                        xs = [n.getCoord()[0] for n in nodes]
                        ys = [n.getCoord()[1] for n in nodes]
                        pos_inter[idx] = [sum(xs)/len(xs), sum(ys)/len(ys)]
                except:
                    pass

        data['intersection'].x = x_inter
        data['intersection'].pos = torch.tensor(pos_inter, dtype=torch.float)

        # B. Lane Features & Positions
        x_lane = torch.zeros((self.num_lanes, GraphConfig.LANE_INPUT_DIM), dtype=torch.float)
        pos_lane = [[0.0, 0.0] for _ in range(self.num_lanes)]

        for lane_id, info in snapshot['lanes'].items():
            if lane_id in self.lane_map:
                idx = self.lane_map[lane_id]
                # Features
                x_lane[idx, 0] = float(info['queue_length'])
                x_lane[idx, 1] = float(info['avg_speed'])
                x_lane[idx, 2] = float(info['waiting_time'])
                
                # Position (Calculate Center of Lane)
                try:
                    lane_shape = self.net.getLane(lane_id).getShape()
                    if lane_shape:
                        # Calculate simple centroid (average of all shape points)
                        avg_x = sum(p[0] for p in lane_shape) / len(lane_shape)
                        avg_y = sum(p[1] for p in lane_shape) / len(lane_shape)
                        pos_lane[idx] = [avg_x, avg_y]
                except:
                    pass # Keep default 0.0 if shape retrieval fails

        data['lane'].x = x_lane
        data['lane'].pos = torch.tensor(pos_lane, dtype=torch.float)

        # --- 2. Edges (Static) ---
        if self.static_edges['part_of'].numel() > 0:
            data['lane', 'part_of', 'intersection'].edge_index = self.static_edges['part_of']
            # [NEW] Attach the physical attributes to the graph
            data['lane', 'part_of', 'intersection'].edge_attr = self.static_edges['part_of_attr']
        
        if self.static_edges['adjacent'].numel() > 0:
            data['intersection', 'adjacent_to', 'intersection'].edge_index = self.static_edges['adjacent']
            
        if self.static_edges['feeds'].numel() > 0:
            data['lane', 'feeds_into', 'lane'].edge_index = self.static_edges['feeds']

        return data