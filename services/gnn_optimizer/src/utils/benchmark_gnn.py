import os
import sys
import torch
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

# 1. Setup Project Paths
# Ensure we can import from src
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.graphBuilder.sumo_manager import SumoManager
from src.graphBuilder.graph_builder import TrafficGraphBuilder
from src.models.hgat_core import RecurrentHGAT
from src.config import SimConfig, GraphConfig, TrainConfig, ModelConfig

# --- Configuration ---
STEPS = 1000               # Simulation duration
SEED = 42                  # Fixed seed for fairness
MODEL_PATH = "experiments/saved_models/final_marl_model.pth"
PLOT_DIR = "experiments/plots"

def get_metrics(snapshot):
    """
    Extracts raw performance metrics from the SUMO snapshot.
    We look at Queue Length and Waiting Time as defined in your reward_function.py.
    """
    total_queue = 0
    total_wait = 0
    
    for lane_id, info in snapshot['lanes'].items():
        total_queue += info['queue_length']
        total_wait += info['waiting_time']
        
    return total_queue, total_wait

def run_baseline():
    """
    Runs the simulation with SUMO's default traffic light logic (No AI).
    """
    print(f"\n[Baseline] Starting simulation (Seed {SEED})...")
    manager = SumoManager(SimConfig.SUMO_CFG, use_gui=False)
    manager.start()
    manager.step() # Init
    
    queues = []
    waits = []

    for t in range(STEPS):
        manager.step()
        
        # Capture metrics
        snap = manager.get_snapshot()
        q, w = get_metrics(snap)
        queues.append(q)
        waits.append(w)

        if t % 200 == 0:
            print(f"   Step {t}: Queue={q}")

    manager.close()
    return np.array(queues), np.array(waits)

def run_gnn_model():
    """
    Runs the simulation controlled by your trained GNN model.
    """
    print(f"\n[GNN Agent] Starting simulation (Seed {SEED})...")
    
    # Init Managers
    manager = SumoManager(SimConfig.SUMO_CFG, use_gui=False)
    graph_builder = TrafficGraphBuilder(SimConfig.NET_FILE)
    manager.start()
    manager.step()
    
    # Load Model
    snapshot = manager.get_snapshot()
    data = graph_builder.create_hetero_data(snapshot)
    
    model = RecurrentHGAT(
        hidden_channels=TrainConfig.HIDDEN_DIM, 
        out_channels=GraphConfig.NUM_SIGNAL_PHASES, 
        num_heads=ModelConfig.NUM_HEADS, 
        metadata=data.metadata()
    )
    
    try:
        model.load_state_dict(torch.load(MODEL_PATH, map_location='cpu'))
        model.eval()
        print(f"   Model loaded: {MODEL_PATH}")
    except Exception as e:
        print(f"   Error loading model: {e}")
        manager.close()
        return np.array([]), np.array([])

    # Simulation Loop
    queues = []
    waits = []
    hidden_state = None
    ACTION_INTERVAL = 15
    idx_to_id = {v: k for k, v in graph_builder.tls_map.items()}

    for t in range(STEPS):
        # AI Logic
        if t % ACTION_INTERVAL == 0:
            snapshot = manager.get_snapshot()
            data = graph_builder.create_hetero_data(snapshot)
            
            with torch.no_grad():
                out = model(data.x_dict, data.edge_index_dict, hidden_state)
                # Handle model output variations (Tuple vs Tensor)
                if isinstance(out, tuple):
                    logits = out[0]
                    hidden_state = out[-1]
                else:
                    logits = out

                actions = torch.argmax(logits, dim=1).tolist()
                
                # Apply actions
                actions_dict = {}
                for idx, val in enumerate(actions):
                    if idx in idx_to_id:
                        tls_id = idx_to_id[idx]
                        phase = 2 if val == 1 else 0 
                        actions_dict[tls_id] = phase
                
                manager.apply_actions(actions_dict)
        
        manager.step()
        
        # Capture metrics
        snap = manager.get_snapshot()
        q, w = get_metrics(snap)
        queues.append(q)
        waits.append(w)
        
        if t % 200 == 0:
            print(f"   Step {t}: Queue={q}")

    manager.close()
    return np.array(queues), np.array(waits)

def save_comparison_plots(base_q, base_w, gnn_q, gnn_w, imp_q, imp_w):
    if not os.path.exists(PLOT_DIR):
        os.makedirs(PLOT_DIR)

    # Plot 1: Queue Length
    plt.figure(figsize=(12, 5))
    plt.plot(base_q, label='Baseline (Default)', color='grey', alpha=0.6, linestyle='--')
    plt.plot(gnn_q, label='GNN Model', color='green', linewidth=2)
    plt.title(f'Traffic Congestion Comparison (Improvement: {imp_q:.2f}%)')
    plt.xlabel('Simulation Steps')
    plt.ylabel('Total Queue Length (Vehicles)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{PLOT_DIR}/benchmark_queue.png")
    plt.close()

    # Plot 2: Waiting Time
    plt.figure(figsize=(12, 5))
    plt.plot(base_w, label='Baseline (Default)', color='grey', alpha=0.6, linestyle='--')
    plt.plot(gnn_w, label='GNN Model', color='blue', linewidth=2)
    plt.title(f'Waiting Time Comparison (Improvement: {imp_w:.2f}%)')
    plt.xlabel('Simulation Steps')
    plt.ylabel('Accumulated Waiting Time (s)')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(f"{PLOT_DIR}/benchmark_wait.png")
    plt.close()

def main():
    print("="*40)
    print("  TRAFFIC OPTIMIZATION BENCHMARK")
    print("="*40)

    # 1. Run Simulations
    base_q, base_w = run_baseline()
    gnn_q, gnn_w = run_gnn_model()

    if len(gnn_q) == 0:
        print("GNN Simulation failed. Exiting.")
        return

    # 2. Calculate Statistics
    avg_base_q = np.mean(base_q)
    avg_gnn_q = np.mean(gnn_q)
    
    avg_base_w = np.mean(base_w)
    avg_gnn_w = np.mean(gnn_w)

    # Calculate Percentage Improvement
    # (Baseline - New) / Baseline * 100
    imp_q = ((avg_base_q - avg_gnn_q) / avg_base_q) * 100 if avg_base_q > 0 else 0
    imp_w = ((avg_base_w - avg_gnn_w) / avg_base_w) * 100 if avg_base_w > 0 else 0

    # 3. Report
    print("\n" + "-"*40)
    print("RESULTS SUMMARY")
    print("-"*40)
    print(f"{'Metric':<20} | {'Baseline':<10} | {'GNN Model':<10} | {'Improvement':<10}")
    print("-" * 58)
    print(f"{'Avg Queue Length':<20} | {avg_base_q:<10.2f} | {avg_gnn_q:<10.2f} | {imp_q:+.2f}%")
    print(f"{'Avg Waiting Time':<20} | {avg_base_w:<10.2f} | {avg_gnn_w:<10.2f} | {imp_w:+.2f}%")
    print("-" * 58)

    # 4. Save Plots
    save_comparison_plots(base_q, base_w, gnn_q, gnn_w, imp_q, imp_w)
    print(f"\n plots saved to {PLOT_DIR}")

if __name__ == "__main__":
    main()