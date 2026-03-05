import torch
import torch.nn.functional as F
import os
import threading
from torch_geometric.data import Batch

# Ensure imports to the parent src folder exist or structure properly
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../gnn_optimizer')))

from src.graphBuilder.graph_builder import TrafficGraphBuilder
from src.models.hgat_core import RecurrentHGAT
from src.config import TrainConfig, ModelConfig, GraphConfig

class GNNPredictor:
    def __init__(self):
        self._lock = threading.Lock()
        self.model_path = os.getenv('MODEL_PATH', '/app/weights/final_marl_model_best.pth')
        self.graph_builder = None
        self.model = None
        self.hidden_state = None
        
        # Load weights ONCE at startup — they never change
        self._weights_cache = None
        self._load_weights_once()

    def _load_weights_once(self):
        """Loads checkpoint from disk once. Stored in memory for reuse."""
        self._weights_cache = torch.load(self.model_path, map_location='cpu', weights_only=True)
        print(f'Weights loaded into cache from {self.model_path}')

    def initialize_graph(self, net_path: str):
        """Rebuilds graph for new map. Reuses cached weights — does NOT re-read disk."""
        with self._lock:
            print(f'Building traffic graph for: {net_path}')
            self.graph_builder = TrafficGraphBuilder(net_path)
            
            # Build model architecture for new graph metadata
            tls_ids  = list(self.graph_builder.tls_map.keys())
            lane_ids = [l.getID() for l in self.graph_builder.all_lanes]
            
            dummy = {
                'intersections': {t: {'phase_index': 0, 'time_to_switch': 0} for t in tls_ids},
                'lanes': {l: {'queue_length': 0, 'avg_speed': 0, 'waiting_time': 0} for l in lane_ids}
            }
            
            data = self.graph_builder.create_hetero_data(dummy)
            self.model = RecurrentHGAT(
                hidden_channels=TrainConfig.HIDDEN_DIM,
                out_channels=GraphConfig.NUM_ACTIONS,
                num_heads=ModelConfig.NUM_HEADS,
                metadata=data.metadata()
            )
            self.model.load_state_dict(self._weights_cache)  # Load from memory — instant
            self.model.eval()
            self.hidden_state = None  # Reset GRU memory for the new map
            print(f'Graph ready: {len(tls_ids)} intersections, {len(lane_ids)} lanes')

    def predict(self, snapshot: dict):
        with self._lock:
            if self.model is None or self.graph_builder is None:
                print("Warning: predict called before graph was initialized.")
                return {}, 0.0
                
            data = self.graph_builder.create_hetero_data(snapshot)
            num_inter = data['intersection'].x.shape[0]
            
            self.model.mc_dropout.enable_mc_dropout()
            batched = Batch.from_data_list([data] * 20)
            b_hidden = self.hidden_state.repeat(20, 1) if self.hidden_state is not None else None
            
            with torch.no_grad():
                b_logits, _, _ = self.model(batched.x_dict, batched.edge_index_dict, b_hidden, batched.edge_attr_dict)
            
            probs = F.softmax(b_logits, dim=1).view(20, num_inter, -1)
            mean_probs = probs.mean(0)
            uncertainty = probs.std(0).mean().item()
            self.model.mc_dropout.disable_mc_dropout()
            
            with torch.no_grad():
                _, _, self.hidden_state = self.model(data.x_dict, data.edge_index_dict, self.hidden_state, data.edge_attr_dict)
                
            chosen = torch.argmax(mean_probs, dim=1).tolist()
            idx_to_id = {v: k for k, v in self.graph_builder.tls_map.items()}
            actions = {idx_to_id[i]: chosen[i] for i in range(len(chosen)) if i in idx_to_id}
            
            return actions, uncertainty

    def reset(self):
        with self._lock:
            self.hidden_state = None
