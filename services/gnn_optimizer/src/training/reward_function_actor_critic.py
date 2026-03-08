# src/training/reward_function_actor_critic.py
import numpy as np

def calculate_reward(snapshot, graph_builder):
    """
    IMPROVED Localized Max Pressure Reward with:
    1. Proper scaling (no /100 killing gradients)
    2. Linear pressure core (stable) + soft wait penalty
    3. Throughput BONUS (positive signal the paper lacks)
    4. Neighbor pressure sharing (your localization advantage)
    """
    num_tls = graph_builder.num_intersections
    local_rewards = np.zeros(num_tls)

    # --- Pass 1: Calculate local reward per intersection ---
    for tls_id, tls_idx in graph_builder.tls_map.items():
        incoming_queue = 0.0
        outgoing_queue = 0.0
        total_wait = 0.0
        vehicles_moving = 0.0
        num_incoming_lanes = 0

        if tls_id not in graph_builder.tls_to_nodes:
            continue

        for node in graph_builder.tls_to_nodes[tls_id]:
            # Incoming lanes: what's demanding green
            for inc_edge in node.getIncoming():
                for lane in inc_edge.getLanes():
                    l_id = lane.getID()
                    if l_id not in snapshot['lanes']:
                        continue
                    data = snapshot['lanes'][l_id]
                    incoming_queue += data['queue_length']
                    total_wait += data['waiting_time']
                    num_incoming_lanes += 1

                    # Throughput bonus: moving vehicles are a positive signal
                    # avg_speed > 0.5 m/s means vehicle is actually moving
                    if data['avg_speed'] > 0.5:
                        vehicles_moving += data['avg_speed'] / 13.89  # normalize by max speed

            # Outgoing lanes: spillback detection
            for out_edge in node.getOutgoing():
                for lane in out_edge.getLanes():
                    l_id = lane.getID()
                    if l_id in snapshot['lanes']:
                        outgoing_queue += snapshot['lanes'][l_id]['queue_length']

        # --- Core: Linear Max Pressure (stable, proven) ---
        pressure = incoming_queue - outgoing_queue

        # --- Wait Penalty: Soft, activates early ---
        # Normalize per lane to prevent scale explosion
        if num_incoming_lanes > 0:
            avg_wait = total_wait / num_incoming_lanes
        else:
            avg_wait = 0.0
        # Soft penalty: grows linearly after 30s, harshly after 90s
        if avg_wait < 30.0:
            wait_penalty = 0.0
        elif avg_wait < 90.0:
            wait_penalty = (avg_wait - 30.0) / 60.0  # 0 to 1 range
        else:
            wait_penalty = 1.0 + (avg_wait - 90.0) / 90.0  # exceeds 1 for severe cases

        # --- Throughput Bonus (your advantage over the paper) ---
        throughput_bonus = vehicles_moving / max(num_incoming_lanes, 1)

        # --- Final Composition ---
        # Scale: pressure in range [-30, 30], wait_penalty in [0, 2], bonus in [0, 1]
        # Target reward range: approximately [-1, 0.5] per intersection
        reward = (
            -abs(pressure) / 30.0          # Pressure penalty (normalized)
            - 0.3 * wait_penalty            # Wait penalty (weighted)
            + 0.1 * throughput_bonus        # Throughput bonus (small positive)
        )

        local_rewards[tls_idx] = reward

    # --- Pass 2: Localized Neighbor Sharing (YOUR KEY INNOVATION) ---
    # Each agent gets a fraction of its neighbors' rewards
    # This is better than the paper's global reward: more targeted
    NEIGHBOR_DISCOUNT = 0.3  # ψ in the paper, but localized
    global_rewards = local_rewards.copy()

    if graph_builder.static_edges['adjacent'].numel() > 0:
        adj = graph_builder.static_edges['adjacent']
        for edge_idx in range(adj.shape[1]):
            src_idx = adj[0, edge_idx].item()
            dst_idx = adj[1, edge_idx].item()
            # Agent at src gets partial credit for neighbor at dst
            global_rewards[src_idx] += NEIGHBOR_DISCOUNT * local_rewards[dst_idx]

    return global_rewards