import sys
import os
import torch
import torch.nn.functional as F

# ==============================================================================
# 1. PATH FIX: Register 'gnn_optimizer' directory
# ==============================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
gnn_project_path = os.path.abspath(os.path.join(current_dir, "../../../services/gnn_optimizer"))

if gnn_project_path not in sys.path:
    sys.path.append(gnn_project_path)

# Import your existing Engine and Configs
from src.inference.engine import RealTimeInferenceEngine
# FIX: Added GraphConfig to imports
from src.config import SimConfig, FileConfig, TrainConfig, ModelConfig, GraphConfig
from src.models.hgat_core import RecurrentHGAT 

# ==============================================================================
# 2. THE PASSIVE ADAPTER
# ==============================================================================
class PassiveRealTimeEngine(RealTimeInferenceEngine):
    """
    A subclass of your existing engine that disables SUMO control.
    It acts as a 'Navigator' (Predictor) rather than a 'Driver'.
    """
    def initialize_model(self):
        print(f"🔌 Initializing GNN Model (Passive Mode)...")
        
        # CRITICAL CHANGE: We do NOT call self.manager.start() 
        # because SimulationController has already started SUMO.
        
        # We try to get a snapshot from the RUNNING simulation to build metadata
        try:
            # We assume traci is already active. 
            # We skip self.manager.step() to avoid desyncing the Controller.
            snapshot = self.manager.get_snapshot()
            data = self.graph_builder.create_hetero_data(snapshot)
        except Exception as e:
            print(f"⚠️ Warning: Could not fetch initial snapshot (SUMO might not be ready). Using dummy metadata.")
            # Fallback: Create dummy data if called before simulation start
            # This ensures model loading doesn't fail
            snapshot = self._create_dummy_snapshot()
            data = self.graph_builder.create_hetero_data(snapshot)

        # --- REUSE YOUR EXISTING LOADING LOGIC ---
        try:
            # FIX: Use GraphConfig.NUM_SIGNAL_PHASES instead of hardcoded 4
            self.model = RecurrentHGAT(
                hidden_channels=TrainConfig.HIDDEN_DIM,
                out_channels=GraphConfig.NUM_SIGNAL_PHASES, # <--- CHANGED THIS (was 4)
                num_heads=ModelConfig.NUM_HEADS,
                metadata=data.metadata()
            )
            
            print(f"📥 Loading weights from: {self.model_path}")
            checkpoint = torch.load(self.model_path, map_location=torch.device('cpu'), weights_only=True)
            self.model.load_state_dict(checkpoint)
            self.model.eval()
            print("✅ Model Loaded Successfully!")
            
        except Exception as e:
            print(f"❌ Model Load Error: {e}")
            raise e

    def _create_dummy_snapshot(self):
        """Helper to create fake data just to initialize model architecture"""
        tls_ids = self.graph_builder.tls_map.keys()
        return {
            "intersections": {id: {"phase_index": 0, "time_to_switch": 0} for id in tls_ids},
            "lanes": {} 
        }

# ==============================================================================
# 3. THE OPTIMIZER CLASS (Used by SimulationController)
# ==============================================================================
class GNNTrafficOptimizer:
    def __init__(self, model_path=None, net_path=None):
        """
        Initializes the optimizer with the specific map used by the Control Panel.
        """
        if not net_path:
            raise ValueError("❌ net_path is required! The Optimizer must know which map the Simulation is using.")
        
        # Use provided paths
        self.net_path = net_path 
        # Default to the trained model path if not overwritten
        self.model_path = model_path if model_path else FileConfig.FINAL_MARL_MODEL_PATH
        
        print(f"🗺️ GNN Adapter: Building Graph for Network: {self.net_path}")

        # Initialize the PASSIVE engine with the DYNAMIC map
        self.engine = PassiveRealTimeEngine(
            config_path="", 
            net_path=self.net_path,
            model_path=self.model_path,
            use_gui=False
        )
        
        self.engine.initialize_model()
        self.hidden_state = None

    def predict(self, raw_sumo_data):
        # 1. Data Prep
        data = self.engine.graph_builder.create_hetero_data(raw_sumo_data)
        
        # ---------------------------------------------------------
        # [START] UPDATED UNCERTAINTY LOGIC
        # ---------------------------------------------------------
        
        self.engine.model.mc_dropout.enable_mc_dropout()
        
        num_samples = 20
        probability_samples = []  # Changed list name for clarity

        with torch.no_grad():
            for _ in range(num_samples):
                # Get raw logits
                sample_logits, _, _ = self.engine.model(
                    data.x_dict, 
                    data.edge_index_dict, 
                    self.hidden_state
                )
                
                # --- FIX: Convert Logits to Probabilities (0.0 to 1.0) ---
                sample_probs = F.softmax(sample_logits, dim=1)
                probability_samples.append(sample_probs)

        # Calculate Statistics on PROBABILITIES
        stack = torch.stack(probability_samples) # Shape: [20, Batch, Actions]
        
        # The Action is the MEAN of probabilities
        mean_probs = stack.mean(dim=0)
        
        # Uncertainty = Standard Deviation of Probabilities
        # A value of 0.1 means the confidence fluctuates by 10%
        uncertainty_score = stack.std(dim=0).mean().item()

        self.engine.model.mc_dropout.disable_mc_dropout()

        # Update state (Deterministic pass)
        with torch.no_grad():
            _, _, self.hidden_state = self.engine.model(
                data.x_dict, 
                data.edge_index_dict, 
                self.hidden_state
            )

        print(f"📊 GNN Confidence | Uncertainty (Prob. StdDev): {uncertainty_score:.5f}")
        
        # Adjust Threshold: 0.1 is now a significant fluctuation in probability
        if uncertainty_score > 0.15: 
             print("⚠️  High Model Uncertainty Detected!")

        # ---------------------------------------------------------
        # [END] UPDATED LOGIC
        # ---------------------------------------------------------
        
        # 3. Select Action from Mean Probabilities
        chosen_phases = torch.argmax(mean_probs, dim=1).tolist()
        
        # ... rest of your mapping code ...
        idx_to_id = {v: k for k, v in self.engine.graph_builder.tls_map.items()}
        actions_dict = {}
        # ... (keep existing loop) ...
        for idx, model_action in enumerate(chosen_phases):
            if idx not in idx_to_id: continue
            tls_id = idx_to_id[idx]
            
            manager_target_idx = 0 
            if model_action == 0: manager_target_idx = 0 
            elif model_action == 1: manager_target_idx = 1
            else: manager_target_idx = 0
            
            actions_dict[tls_id] = manager_target_idx
            
        return actions_dict

    def reset(self):
        self.hidden_state = None