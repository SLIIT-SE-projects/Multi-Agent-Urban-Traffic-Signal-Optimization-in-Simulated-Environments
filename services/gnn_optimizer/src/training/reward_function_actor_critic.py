import numpy as np

def calculate_reward(snapshot, graph_builder):
    """
    Calculates Localized Max Pressure Rewards. 
    Pressure = (Incoming Queue Lengths) - (Outgoing Queue Lengths)
    """
    num_tls = graph_builder.num_intersections
    tls_rewards = np.zeros(num_tls)
    
    for tls_id, tls_idx in graph_builder.tls_map.items():
        incoming_queue = 0
        outgoing_queue = 0
        wait_penalty = 0
        
        # 1. Calculate Max Pressure for this specific intersection
        if tls_id in graph_builder.tls_to_nodes:
            for node in graph_builder.tls_to_nodes[tls_id]:
                
                # A. Tally Incoming Vehicles (Demanding a green light)
                for inc_edge in node.getIncoming():
                    for lane in inc_edge.getLanes():
                        l_id = lane.getID()
                        if l_id in snapshot['lanes']:
                            data = snapshot['lanes'][l_id]
                            incoming_queue += data['queue_length']
                            
                            # Add starvation penalty only for incoming lanes
                            wait = data['waiting_time']
                            if wait > 120:
                                wait_penalty += wait * 1.5
                            elif wait > 60:
                                wait_penalty += wait * 0.5

                # B. Tally Outgoing Vehicles (Measuring downstream spillback)
                for out_edge in node.getOutgoing():
                    for lane in out_edge.getLanes():
                        l_id = lane.getID()
                        if l_id in snapshot['lanes']:
                            # If outgoing is full, we DO NOT want to send cars there
                            outgoing_queue += snapshot['lanes'][l_id]['queue_length']

        # 2. The Pressure Equation
        # If incoming is 20 and outgoing is 0 -> Pressure is 20 (We must clear it)
        # If incoming is 20 but outgoing is 30 -> Pressure is -10 (Do NOT turn green, will cause gridlock)
        pressure = incoming_queue - outgoing_queue
        
        # 3. Penalty Calculation
        # We square the pressure so the AI prioritizes the worst intersections first
        pressure_penalty = (pressure ** 2) / 5.0
        
        # We return a negative reward (penalty) to the Critic
        tls_rewards[tls_idx] = - (pressure_penalty + wait_penalty) / 100.0

    return tls_rewards