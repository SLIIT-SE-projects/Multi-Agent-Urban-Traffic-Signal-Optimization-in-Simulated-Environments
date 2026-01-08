"""
Training Script for Traffic LSTM.
Generates a dataset from SUMO and trains the model.
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os
import logging
import sys
import os

# Add src to path so traffic_mpc can be imported
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from traffic_mpc.config.settings import SumoConfig, MPCConfig, AppConfig
from traffic_mpc.interface.sumo_client import SumoClient
from traffic_mpc.core.prediction import TrafficLSTM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TRAINER")

def generate_data(steps=3000):
    """Runs simulation to gather training data."""
    logger.info("--- Generating Training Data ---")
    
    # 1. Setup Config
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(base_dir, "../emergency_vehicle_preemption/simulation/config/katunayake.sumocfg")
    
    sumo_cfg = SumoConfig(
        sumo_binary="sumo", # Headless for speed
        config_file=scenario_path,
        use_gui=False
    )
    
    client = SumoClient(sumo_cfg)
    client.start()
    
    # Discovery
    client.step()
    detectors = client.get_detector_data()
    # Remove e2_ prefix
    lane_ids = sorted([d.replace("e2_", "") for d in detectors.keys()])
    
    data_buffer = []
    
    try:
        for _ in range(steps):
            client.step()
            raw_data = client.get_detector_data()
            # Convert dict to vector
            snapshot = [raw_data.get(f"e2_{lid}", 0.0) for lid in lane_ids]
            data_buffer.append(snapshot)
    finally:
        client.close()
        
    return np.array(data_buffer), lane_ids

def create_sequences(data, seq_len, pred_len):
    """Creates X (History) and Y (Target) sequences."""
    xs, ys = [], []
    for i in range(len(data) - seq_len - pred_len):
        x = data[i : i+seq_len]
        y = data[i+seq_len : i+seq_len+pred_len]
        xs.append(x)
        ys.append(y.flatten()) 
    return np.array(xs), np.array(ys)

def train():
    os.makedirs("data", exist_ok=True)
    
    # 1. Generate Data
    raw_data, lane_ids = generate_data()
    logger.info(f"Collected Data Shape: {raw_data.shape}")
    
    # 2. Prepare Tensors
    seq_len = 10 
    pred_len = 20 # Must match config.mpc.prediction_horizon (default 20)
    
    X, Y = create_sequences(raw_data, seq_len, pred_len)
    
    X_tensor = torch.FloatTensor(X)
    Y_tensor = torch.FloatTensor(Y)
    
    # 3. Train
    n_lanes = len(lane_ids)
    model = TrafficLSTM(n_lanes, 64, n_lanes * pred_len)
    
    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    
    logger.info("--- Starting Training ---")
    epochs = 50
    for epoch in range(epochs):
        optimizer.zero_grad()
        outputs = model(X_tensor)
        loss = criterion(outputs, Y_tensor)
        loss.backward()
        optimizer.step()
        
        if epoch % 10 == 0:
            logger.info(f"Epoch {epoch} Loss: {loss.item():.4f}")

    # 4. Save
    model_path = "data/model.pth"
    torch.save(model.state_dict(), model_path)
    logger.info(f"Model saved to {model_path}")

if __name__ == "__main__":
    train()