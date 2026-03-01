import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import HeteroConv, GATConv, Linear

# --- IMPORT THE NEW MODULES ---
from src.config import ModelConfig, GraphConfig # [NEW] Imported GraphConfig for edge dimension
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

        # 2. Spatial GNN Layers
        # [NEW] Added edge_dim to the GATConv so it learns from road capacity
        self.conv1 = HeteroConv({
            ('lane', 'part_of', 'intersection'): GATConv(
                (-1, -1), hidden_channels, heads=num_heads, add_self_loops=False,
                edge_dim=GraphConfig.EDGE_INPUT_DIM # <--- Reads edge features
            ),
            ('intersection', 'adjacent_to', 'intersection'): GATConv((-1, -1), hidden_channels, heads=num_heads, add_self_loops=False),
            ('lane', 'feeds_into', 'lane'): GATConv((-1, -1), hidden_channels, heads=num_heads, add_self_loops=False)
        }, aggr='sum')

        # 3. Temporal Recurrent Layer.
        gnn_out_dim = hidden_channels * num_heads
        self.gru = nn.GRUCell(gnn_out_dim, hidden_channels)

        # 4. Uncertainty Module 
        self.mc_dropout = BayesianDropout(p=ModelConfig.DROPOUT_RATE)

        # 5. Actor-Critic Head
        self.policy_head = TrafficPolicyHead(hidden_channels, out_channels)

    # [NEW] Added edge_attr_dict parameter to accept the physical features
    def forward(self, x_dict, edge_index_dict, hidden_state=None, edge_attr_dict=None):
        # 1. Encode Raw Features
        x_dict_encoded = {}
        for node_type, x in x_dict.items():
            x_dict_encoded[node_type] = F.relu(self.encoder_dict[node_type](x))

        # 2. [Uncertainty Injection 1]: Spatial Processing (GNN)
        # [NEW] Pass the edge attributes into the convolution layer
        if edge_attr_dict is not None:
            x_dict_out = self.conv1(x_dict_encoded, edge_index_dict, edge_attr_dict=edge_attr_dict)
        else:
            raise ValueError("edge_attr_dict is required because GATConv expects EDGE_INPUT_DIM.")
        
        # Apply Activation & The Custom Dropout
        x_dict_out = {k: self.mc_dropout(F.relu(v)) for k, v in x_dict_out.items()}
        
        # 3. Temporal Processing (GRU)
        intersection_embeddings = x_dict_out['intersection']
        
        if hidden_state is None:
            hidden_state = torch.zeros_like(intersection_embeddings[:, :self.hidden_channels])

        # Update memory
        new_hidden_state = self.gru(intersection_embeddings, hidden_state)

        # [Uncertainty Injection 2]: Policy Decision Boundary
        policy_input = self.mc_dropout(new_hidden_state)
        
        # 4. Decision Making (Actor & Critic)
        action_logits, state_value = self.policy_head(policy_input)
        
        return action_logits, state_value, new_hidden_state