import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import HeteroConv, GATConv, Linear

from src.config import ModelConfig, GraphConfig 
from src.models.policy_head import TrafficPolicyHead
from src.models.uncertainty import BayesianDropout

class RecurrentHGAT(nn.Module):
    def __init__(self, hidden_channels, out_channels, num_heads, metadata):
        super().__init__()

        self.hidden_channels = hidden_channels
        
        # 1. Input Encoders (Feature Projection) 
        self.encoder_dict = nn.ModuleDict()
        self.encoder_dict['intersection'] = Linear(-1, hidden_channels)
        self.encoder_dict['lane'] = Linear(-1, hidden_channels)

        # ------------------------------------------------------------------
        # FIX 1: TWO-LAYER GNN (Prevents DDP Crash & Adds Spillback Awareness)
        # ------------------------------------------------------------------
        
        # LAYER 1: Local Entity Context (Lanes -> Lanes, Intersections -> Intersections)
        # concat=False keeps dimension at hidden_channels for the residual connection
        self.conv1_context = HeteroConv({
            ('lane', 'feeds_into', 'lane'): GATConv((-1, -1), hidden_channels, heads=num_heads, concat=False, add_self_loops=False),
            ('intersection', 'adjacent_to', 'intersection'): GATConv((-1, -1), hidden_channels, heads=num_heads, concat=False, add_self_loops=False)
        }, aggr='sum')

        # LAYER 2: Target Aggregation (Updated Lanes -> Intersections)
        # concat=True outputs (hidden_channels * num_heads) to feed the GRU perfectly
        self.conv2_target = HeteroConv({
            ('lane', 'part_of', 'intersection'): GATConv(
                (-1, -1), hidden_channels, heads=num_heads, concat=True, add_self_loops=False,
                edge_dim=GraphConfig.EDGE_INPUT_DIM # <--- Reads edge features
            )
        }, aggr='sum')

        # 3. Temporal Recurrent Layer.
        gnn_out_dim = hidden_channels * num_heads
        self.gru = nn.GRUCell(gnn_out_dim, hidden_channels)

        # 4. Uncertainty Module 
        self.mc_dropout = BayesianDropout(p=ModelConfig.DROPOUT_RATE)

        # 5. Actor-Critic Head
        self.policy_head = TrafficPolicyHead(hidden_channels, out_channels)

    def forward(self, x_dict, edge_index_dict, hidden_state=None, edge_attr_dict=None):
        
        # ------------------------------------------------------------------
        # FIX 2: THE NONE CRASH FALLBACK FOR EDGE ATTRIBUTES
        # ------------------------------------------------------------------
        if edge_attr_dict is None:
            edge_type = ('lane', 'part_of', 'intersection')
            if edge_type in edge_index_dict:
                # Dynamically calculate how many edges exist in the current batch
                num_edges = edge_index_dict[edge_type].size(1)
                device = edge_index_dict[edge_type].device
                # Generate a dummy tensor of zeros to prevent matrix multiplication crash
                dummy_attr = torch.zeros((num_edges, GraphConfig.EDGE_INPUT_DIM), dtype=torch.float32, device=device)
                edge_attr_dict = {edge_type: dummy_attr}

        # 1. Encode Raw Features
        x_dict_encoded = {}
        for node_type, x in x_dict.items():
            x_dict_encoded[node_type] = F.relu(self.encoder_dict[node_type](x))

        # 2. Spatial Processing: Layer 1 (Contextualize)
        # Calculates lane-to-lane flow and intersection coordination
        x_dict_context = self.conv1_context(x_dict_encoded, edge_index_dict)
        
        # Apply Residual Connection (Merge Context with Original Encodings)
        x_dict_res = {}
        for k in x_dict_encoded.keys():
            if k in x_dict_context:
                x_dict_res[k] = F.relu(x_dict_encoded[k] + x_dict_context[k])
            else:
                x_dict_res[k] = x_dict_encoded[k]

        # 3. Spatial Processing: Layer 2 (Target)
        # Feeds the contextually-aware lanes into the intersection via edge features
        x_dict_out = self.conv2_target(x_dict_res, edge_index_dict, edge_attr_dict=edge_attr_dict)

        # 4. Extract and process Intersection Node (DDP safe, all graphs utilized)
        intersection_embeddings = self.mc_dropout(F.relu(x_dict_out['intersection']))
        
        if hidden_state is None:
            hidden_state = torch.zeros_like(intersection_embeddings[:, :self.hidden_channels])

        # Update memory
        new_hidden_state = self.gru(intersection_embeddings, hidden_state)

        # Policy Decision Boundary
        policy_input = self.mc_dropout(new_hidden_state)
        action_logits, state_value = self.policy_head(policy_input)
        
        return action_logits, state_value, new_hidden_state