"""
Demand Prediction Module.
Uses an LSTM neural network to forecast future vehicle arrivals.
"""
import torch
import torch.nn as nn
import numpy as np
import logging
import os
from traffic_mpc.config.settings import MPCConfig

logger = logging.getLogger(__name__)

class TrafficLSTM(nn.Module):
    """Simple LSTM for time-series forecasting."""
    def __init__(self, input_size, hidden_size, output_size):
        super(TrafficLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.lstm = nn.LSTM(input_size, hidden_size, batch_first=True)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        # x shape: (batch, seq_len, input_size)
        out, _ = self.lstm(x)
        # Take the output of the last time step
        out = self.fc(out[:, -1, :])
        return out

class DemandPredictor:
    def __init__(self, config: MPCConfig, lane_ids: list, model_path: str = None):
        self.cfg = config
        self.lane_ids = lane_ids
        self.n_lanes = len(lane_ids)
        
        # 1. Initialize Model Architecture
        # Output size = Lanes * Horizon (Predicting flow for every lane at every future step)
        self.model = TrafficLSTM(
            input_size=self.n_lanes,
            hidden_size=64,
            output_size=self.n_lanes * self.cfg.prediction_horizon
        )
        
        self.model_loaded = False
        if model_path and os.path.exists(model_path):
            try:
                self.model.load_state_dict(torch.load(model_path))
                self.model.eval()
                self.model_loaded = True
                logger.info(f"Loaded LSTM model from {model_path}")
            except Exception as e:
                logger.warning(f"Failed to load model: {e}")
        else:
            logger.info("No pre-trained model found. Running in Heuristic Mode.")

        # 2. History Buffer (Sliding Window)
        # We need the last 10 steps to predict the future
        self.history_steps = 10
        self.history_buffer = [] 

    def update_history(self, current_flows: dict):
        """Add current flow rates to history buffer."""
        # Map flow dict to sorted vector matching lane_ids
        flow_vec = [current_flows.get(lid, 0.0) for lid in self.lane_ids]
        self.history_buffer.append(flow_vec)
        
        # Keep buffer fixed size
        if len(self.history_buffer) > self.history_steps:
            self.history_buffer.pop(0)

    def predict(self) -> np.ndarray:
        """
        Generates demand forecast matrix D [n_lanes, Np].
        """
        horizon = self.cfg.prediction_horizon
        
        # Case A: Trained Model Available
        if self.model_loaded and len(self.history_buffer) == self.history_steps:
            input_tensor = torch.FloatTensor([self.history_buffer]) # Add batch dim
            with torch.no_grad():
                prediction = self.model(input_tensor)
            
            # Reshape [1, n_lanes * horizon] -> [n_lanes, horizon]
            d_matrix = prediction.numpy().reshape(self.n_lanes, horizon)
            return np.maximum(d_matrix, 0.0)
            
        # Case B: Heuristic Prediction (Persistence)
        # "Traffic now is likely to continue for the next few seconds"
        if not self.history_buffer:
            return np.zeros((self.n_lanes, horizon))
            
        last_flow = np.array(self.history_buffer[-1])
        
        # Extrapolate last flow forward
        d_matrix = np.tile(last_flow[:, np.newaxis], (1, horizon)).astype(float)
        
        # Add slight noise to prevent solver singularities
        noise = np.random.normal(0, 0.1, d_matrix.shape)
        d_matrix += noise
        
        return np.maximum(d_matrix, 0.0)