"""
Training Script for Traffic LSTM.
Fix 3: Multi-flow training.
  Generates data at multiple vehicle insertion rates (100, 200, 300, 400 veh/hr)
  and trains on the combined dataset so the LSTM learns high-flow congestion patterns.
"""
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os
import json
import logging
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from traffic_mpc.config.settings import SumoConfig, MPCConfig, AppConfig
from traffic_mpc.interface.sumo_client import SumoClient
from traffic_mpc.core.prediction import TrafficLSTM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TRAINER")

# ── Constants (must match mpc_adapter.py at runtime) ─────────────────────────
LANE_CAPACITY = 20.0   # vehicles — used to normalise queue counts to [0,1]

# ── Flow rates to train on ────────────────────────────────────────────────────
# Include the same flow rates users typically test with (100–400 veh/hr).
# More flow rates = model generalises better across operating conditions.
TRAINING_FLOW_RATES = [100, 200, 300, 400]   # vehicles per hour
STEPS_PER_FLOW = 1000                         # simulation steps per flow rate


def generate_data_for_flow(steps: int, flow_rate_vph: int | None = None):
    """
    Run a headless SUMO simulation and collect normalised queue data.

    Args:
        steps         : number of simulation steps to collect
        flow_rate_vph : vehicles/hour to inject (None = use scenario default)

    Returns:
        (data_array [steps, n_lanes], lane_ids list)
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    scenario_path = os.path.join(
        base_dir, "../../simulation_and_control_panel/scenarios/grid3x3/grid3x3.sumo.cfg")

    sumo_cfg = SumoConfig(
        sumo_binary="sumo",
        config_file=scenario_path,
        use_gui=False,
    )

    client = SumoClient(sumo_cfg)
    client.start()

    # Discover lanes from detectors
    client.step()
    detectors = client.get_detector_data()
    lane_ids = sorted([d.replace("e2_", "") for d in detectors.keys()])

    # Apply flow rate if requested (uses TraCI route/flow injection)
    if flow_rate_vph is not None:
        try:
            import traci
            route_ids = traci.route.getIDList()
            for route_id in route_ids:
                # Set vehicles per hour on each route
                # Convert vph to period (seconds between vehicles)
                period = 3600.0 / flow_rate_vph if flow_rate_vph > 0 else 9999
                traci.route.setParameter(route_id, "period", str(period))
        except Exception as e:
            logger.warning(f"Could not set flow rate {flow_rate_vph}: {e}")

    data_buffer = []
    try:
        for _ in range(steps):
            client.step()
            raw_data = client.get_detector_data()
            snapshot = [raw_data.get(f"e2_{lid}", 0.0) / LANE_CAPACITY for lid in lane_ids]
            data_buffer.append(snapshot)
    finally:
        client.close()

    return np.array(data_buffer), lane_ids


def generate_data(steps=3000):
    """
    Fix 3: Generate training data at MULTIPLE flow rates and concatenate.
    Returns combined data and the lane_ids list.
    """
    logger.info("--- Generating Multi-Flow Training Data ---")
    logger.info(f"Flow rates: {TRAINING_FLOW_RATES} veh/hr · {STEPS_PER_FLOW} steps each")

    all_data = []
    lane_ids = None

    for flow_rate in TRAINING_FLOW_RATES:
        logger.info(f"  Collecting {STEPS_PER_FLOW} steps at {flow_rate} veh/hr…")
        try:
            data, ids = generate_data_for_flow(STEPS_PER_FLOW, flow_rate_vph=flow_rate)
            if lane_ids is None:
                lane_ids = ids
            all_data.append(data)
            logger.info(f"  ✓ {flow_rate} veh/hr: {data.shape[0]} steps, {data.shape[1]} lanes")
        except Exception as e:
            logger.warning(f"  ✗ Failed at {flow_rate} veh/hr: {e}. Skipping.")

    if not all_data:
        raise RuntimeError("No training data was collected — check SUMO config path")

    combined = np.concatenate(all_data, axis=0)
    logger.info(f"Combined dataset: {combined.shape[0]} steps × {combined.shape[1]} lanes")
    return combined, lane_ids


def create_sequences(data, seq_len, pred_len):
    """Creates X (history) and Y (target) sequences for LSTM training."""
    xs, ys = [], []
    for i in range(len(data) - seq_len - pred_len):
        x = data[i: i + seq_len]
        y = data[i + seq_len: i + seq_len + pred_len]
        xs.append(x)
        ys.append(y.flatten())
    return np.array(xs), np.array(ys)


def train():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)

    # 1. Generate multi-flow data
    raw_data, lane_ids = generate_data()
    logger.info(f"Collected Data Shape: {raw_data.shape}")

    # 2. Prepare sequences
    seq_len = 10    # history window the LSTM sees (must match DemandPredictor.history_steps)
    pred_len = 20   # must match MPCConfig.prediction_horizon

    X, Y = create_sequences(raw_data, seq_len, pred_len)
    logger.info(f"Sequences: X={X.shape}, Y={Y.shape}")

    X_tensor = torch.FloatTensor(X)
    Y_tensor = torch.FloatTensor(Y)

    # 3. Build model
    n_lanes = len(lane_ids)
    # Larger hidden size benefits from more varied training data
    hidden_size = 128   # was 64 — more capacity for multi-flow patterns
    model = TrafficLSTM(n_lanes, hidden_size, n_lanes * pred_len)

    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    # Learning rate decay to stabilise training on the larger multi-flow dataset
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)

    # 4. Train
    logger.info("--- Starting Training ---")
    epochs = 100   # more epochs to learn multi-flow patterns (was 50)
    best_loss = float("inf")
    best_state = None

    for epoch in range(epochs):
        optimizer.zero_grad()
        outputs = model(X_tensor)
        loss = criterion(outputs, Y_tensor)
        loss.backward()
        optimizer.step()
        scheduler.step()

        if epoch % 10 == 0:
            logger.info(f"Epoch {epoch:3d}/{epochs}  Loss: {loss.item():.6f}  LR: {scheduler.get_last_lr()[0]:.5f}")

        if loss.item() < best_loss:
            best_loss = loss.item()
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    logger.info(f"Training complete. Best loss: {best_loss:.6f}")

    # 5. Save best model
    if best_state:
        model.load_state_dict(best_state)

    model_path = os.path.join(data_dir, "model.pth")
    torch.save(model.state_dict(), model_path)

    lane_ids_path = os.path.join(data_dir, "lane_ids.json")
    with open(lane_ids_path, "w") as f:
        json.dump(lane_ids, f)

    logger.info(f"✅ Model saved → {model_path}")
    logger.info(f"✅ Lane IDs saved → {lane_ids_path}  ({n_lanes} lanes)")


if __name__ == "__main__":
    train()