"""
Training Script for Traffic LSTM — Katunayake Map.

Katunayake uses a pre-generated route file (katunayake.rou.xml) with fixed trips,
so multi-flow injection is not needed. We collect data at the scenario's natural
demand level across the full 4000-step simulation and train from that.

Output files (separate from grid3x3 model):
  data/model_katunayake.pth
  data/lane_ids_katunayake.json
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

from traffic_mpc.config.settings import SumoConfig, MPCConfig
from traffic_mpc.interface.sumo_client import SumoClient
from traffic_mpc.core.prediction import TrafficLSTM

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TRAINER_KATUNAYAKE")

# ── Constants (must match mpc_adapter.py at runtime) ─────────────────────────
LANE_CAPACITY = 20.0   # vehicles — normalise queue counts to [0,1]

# ── Scenario config ───────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCENARIO_PATH = os.path.join(
    BASE_DIR,
    "../../simulation_and_control_panel/scenarios/Katunayake/katunayake.sumocfg"
)
# Collect data in segments to avoid TraCI timeouts on the 4000-step scenario
STEPS_TO_COLLECT = 2000   # collect first 2000 steps of natural demand


def generate_data():
    """
    Run a headless Katunayake simulation and collect normalised queue data.
    Uses TraCI lane halting counts (same as MPC runtime) — NOT e2 detectors
    because Katunayake has no induction loop detectors.
    Returns (data_array [steps, n_lanes], lane_ids list)
    """
    import traci

    logger.info(f"Loading scenario: {SCENARIO_PATH}")
    if not os.path.exists(SCENARIO_PATH):
        raise FileNotFoundError(f"Scenario not found: {SCENARIO_PATH}")

    sumo_cfg = SumoConfig(
        sumo_binary="sumo",
        config_file=SCENARIO_PATH,
        use_gui=False,
    )

    client = SumoClient(sumo_cfg)
    client.start()

    # Step once so TraCI connection is live
    client.step()

    # ── Discover lanes from traffic light controlled links ────────────────────
    # (Same method used by mpc_adapter._initialize_controllers at runtime)
    tls_ids = traci.trafficlight.getIDList()
    lane_set = set()
    for tls_id in tls_ids:
        links = traci.trafficlight.getControlledLinks(tls_id)
        for connection_list in links:
            for conn in connection_list:
                if conn:
                    incoming_lane = conn[0]   # (incoming, outgoing, via)
                    lane_set.add(incoming_lane)

    lane_ids = sorted(list(lane_set))
    logger.info(f"Discovered {len(lane_ids)} lanes from {len(tls_ids)} traffic lights")

    if len(lane_ids) == 0:
        client.close()
        raise RuntimeError(
            "No lanes found. Check that the Katunayake map has traffic lights "
            "with controlled links accessible via TraCI."
        )

    data_buffer = []
    try:
        for step in range(STEPS_TO_COLLECT - 1):  # -1 because we already stepped once
            try:
                client.step()
                # Read queue using getLastStepHaltingNumber — same as MPC runtime
                snapshot = []
                for lid in lane_ids:
                    try:
                        q = traci.lane.getLastStepHaltingNumber(lid)
                        snapshot.append(q / LANE_CAPACITY)
                    except Exception:
                        snapshot.append(0.0)
                data_buffer.append(snapshot)
                if step % 200 == 0:
                    logger.info(f"  Step {step+1}/{STEPS_TO_COLLECT} collected")
            except Exception as e:
                logger.warning(f"  Step {step} error: {e} — stopping early")
                break
    finally:
        client.close()

    logger.info(f"Collected {len(data_buffer)} steps × {len(lane_ids)} lanes")
    return np.array(data_buffer), lane_ids


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
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)

    # 1. Generate data from Katunayake scenario
    raw_data, lane_ids = generate_data()
    if len(raw_data) == 0:
        raise RuntimeError("No data was collected — check SUMO detectors in Katunayake map")

    logger.info(f"Data shape: {raw_data.shape}")

    # 2. Prepare sequences
    seq_len = 10    # must match DemandPredictor.history_steps
    pred_len = 20   # must match MPCConfig.prediction_horizon

    X, Y = create_sequences(raw_data, seq_len, pred_len)
    logger.info(f"Sequences: X={X.shape}, Y={Y.shape}")

    if len(X) == 0:
        raise RuntimeError("Not enough data to create sequences. Increase STEPS_TO_COLLECT.")

    X_tensor = torch.FloatTensor(X)
    Y_tensor = torch.FloatTensor(Y)

    # 3. Build model — same architecture as grid3x3 (hidden=128 mandatory)
    n_lanes = len(lane_ids)
    logger.info(f"Building LSTM: input={n_lanes} lanes, hidden=128, output={n_lanes * pred_len}")
    model = TrafficLSTM(n_lanes, 128, n_lanes * pred_len)

    criterion = nn.MSELoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=30, gamma=0.5)

    # 4. Train
    logger.info("--- Starting Training (100 epochs) ---")
    epochs = 100
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
            logger.info(
                f"Epoch {epoch:3d}/{epochs}  Loss: {loss.item():.6f}"
                f"  LR: {scheduler.get_last_lr()[0]:.5f}"
            )

        if loss.item() < best_loss:
            best_loss = loss.item()
            best_state = {k: v.clone() for k, v in model.state_dict().items()}

    logger.info(f"Training complete. Best loss: {best_loss:.6f}")

    # 5. Save — separate files from grid3x3 model
    if best_state:
        model.load_state_dict(best_state)

    model_path = os.path.join(data_dir, "model_katunayake.pth")
    torch.save(model.state_dict(), model_path)

    lane_ids_path = os.path.join(data_dir, "lane_ids_katunayake.json")
    with open(lane_ids_path, "w") as f:
        json.dump(lane_ids, f)

    logger.info(f"✅ Model saved → {model_path}")
    logger.info(f"✅ Lane IDs saved → {lane_ids_path}  ({n_lanes} lanes)")
    logger.info("")
    logger.info("Run the backend and switch to Katunayake scenario — MPC will")
    logger.info("auto-load model_katunayake.pth when that map is active.")


if __name__ == "__main__":
    train()
