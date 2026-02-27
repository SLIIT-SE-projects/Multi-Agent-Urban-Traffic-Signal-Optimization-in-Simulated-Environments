import numpy as np
from src.config import TrainConfig

def calculate_reward(snapshot, graph_builder):
    """
    Calculates Localized Rewards. 
    Each intersection only gets penalized for the lanes connected to it.
    """
    num_tls = graph_builder.num_intersections
    # Create an array to hold the specific reward for each intersection
    tls_penalties = np.zeros(num_tls)
    
    for lane_id, data in snapshot['lanes'].items():
        if lane_id not in graph_builder.lane_map:
            continue
            
        queue = data['queue_length']
        wait = data['waiting_time'] 
        
        # 1. Quadratic Queue Penalty (Pushes model to prioritize long queues)
        q_penalty = (queue ** 2) / 10.0
        
        # 2. Waiting Time Penalty
        if wait > 120:
            w_penalty = wait * 5.0
        else:
            w_penalty = wait * 0.2

        lane_penalty = q_penalty + w_penalty
        
        # --- MAP THE PENALTY TO THE SPECIFIC INTERSECTION ---
        # Find which intersection this lane is heading towards
        try:
            lane_obj = graph_builder.net.getLane(lane_id)
            target_node = lane_obj.getEdge().getToNode()
            node_id = target_node.getID()
            
            if node_id in graph_builder.node_to_tls_id:
                tls_id = graph_builder.node_to_tls_id[node_id]
                if tls_id in graph_builder.tls_map:
                    tls_idx = graph_builder.tls_map[tls_id]
                    # Add penalty ONLY to this specific intersection
                    tls_penalties[tls_idx] += lane_penalty
        except:
            pass # Skip if lane topology is missing

    # Return negative penalties as the localized rewards array
    return -tls_penalties / 500.0