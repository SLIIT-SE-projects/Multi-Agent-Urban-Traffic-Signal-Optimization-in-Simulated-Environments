import os
import sys
import torch
import numpy as np
import matplotlib.pyplot as plt

# 1. Setup Project Paths
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.graphBuilder.sumo_manager import SumoManager
from src.graphBuilder.graph_builder import TrafficGraphBuilder
from src.models.hgat_core import RecurrentHGAT
from src.config import SimConfig, GraphConfig, TrainConfig, ModelConfig

# --- Configuration ---
STEPS = 1000               # Simulation duration
SEED = 42                  # Fixed seed for fair comparison
MODEL_PATH = "experiments/saved_models/final_marl_model.pth"
PLOT_DIR = "experiments/plots"

# Set plot style
plt.style.use('bmh') 

def calculate_weighted_cost(queue, wait):
    """
    Calculates 'Total Performance' using the training weights.
    """
    w_q = TrainConfig.W_QUEUE
    w_w = TrainConfig.W_WAIT
    return (w_q * queue) + (w_w * wait)

def get_metrics(snapshot):
    """
    Extracts performance metrics: Queue, Wait, and Average Speed.
    """
    total_queue = 0
    total_wait = 0
    total_speed = 0
    num_lanes = 0
    
    for lane_id, info in snapshot['lanes'].items():
        total_queue += info['queue_length']
        total_wait += info['waiting_time']
        # SUMO returns -1 or varying data for empty lanes sometimes, 
        # generally we take the mean of reported speeds.
        speed = info.get('avg_speed', 0)
        total_speed += speed
        num_lanes += 1
        
    cost = calculate_weighted_cost(total_queue, total_wait)
    
    # Calculate Network Average Speed (m/s)
    # Avoid division by zero
    avg_speed = total_speed / num_lanes if num_lanes > 0 else 0
    
    return total_queue, total_wait, avg_speed, cost

def run_simulation(mode="baseline"):
    """
    Runs the simulation in 'baseline' or 'gnn' mode.
    """
    label = "Baseline (Default)" if mode == "baseline" else "GNN Model"
    print(f"\n[{label}] Starting simulation (Seed {SEED})...")
    
    # 1. Init SUMO
    manager = SumoManager(SimConfig.SUMO_CFG, use_gui=False)
    graph_builder = TrafficGraphBuilder(SimConfig.NET_FILE)
    manager.start()
    manager.step()
    
    # 2. Load Model (if GNN)
    model = None
    hidden_state = None
    
    if mode == "gnn":
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
            return [], [], [], []

    # 3. Simulation Loop
    queues = []
    waits = []
    speeds = []
    costs = []
    
    idx_to_id = {v: k for k, v in graph_builder.tls_map.items()}
    ACTION_INTERVAL = 15

    for t in range(STEPS):
        # AI Control Logic (Only for GNN mode)
        if mode == "gnn" and t % ACTION_INTERVAL == 0:
            snapshot = manager.get_snapshot()
            data = graph_builder.create_hetero_data(snapshot)
            
            with torch.no_grad():
                out = model(data.x_dict, data.edge_index_dict, hidden_state)
                if isinstance(out, tuple):
                    logits = out[0]
                    hidden_state = out[-1]
                else:
                    logits = out

                actions = torch.argmax(logits, dim=1).tolist()
                
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
        q, w, s, c = get_metrics(snap)
        
        queues.append(q)
        waits.append(w)
        speeds.append(s)
        costs.append(c)
        
        if t % 200 == 0:
            print(f"   Step {t}: Queue={q} | Speed={s:.2f} m/s")

    manager.close()
    return np.array(queues), np.array(waits), np.array(speeds), np.array(costs)

def plot_single_metric(base_data, gnn_data, title, ylabel, filename, color, higher_is_better=False):
    """
    Helper function to save a single specific plot.
    """
    x = range(len(base_data))
    plt.figure(figsize=(10, 6))
    
    # Plot Baseline
    plt.plot(x, base_data, label='Baseline (Default)', color='#7f8c8d', linestyle='--', linewidth=1.5)
    
    # Plot GNN
    plt.plot(x, gnn_data, label='GNN Model', color=color, linewidth=2)
    plt.fill_between(x, gnn_data, alpha=0.1, color=color)
    
    # Styling
    plt.title(title, fontsize=14, fontweight='bold')
    plt.ylabel(ylabel, fontsize=12)
    plt.xlabel('Simulation Steps', fontsize=12)
    
    # Dynamic Legend Location
    loc = 'lower right' if higher_is_better else 'upper left'
    plt.legend(loc=loc)
    
    plt.grid(True, alpha=0.3)
    
    # Save
    save_path = f"{PLOT_DIR}/{filename}"
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"   Saved: {save_path}")

def save_all_plots(base_data, gnn_data):
    if not os.path.exists(PLOT_DIR):
        os.makedirs(PLOT_DIR)

    base_q, base_w, base_s, base_c = base_data
    gnn_q, gnn_w, gnn_s, gnn_c = gnn_data
    x = range(len(base_q))

    print("\n[Plotting] Generating graphs...")

    # --- 1. Save Separate Plots ---
    plot_single_metric(base_q, gnn_q, 
                      "Network Congestion (Queue Length)", "Vehicles", 
                      "benchmark_queue.png", "#27ae60", higher_is_better=False)

    plot_single_metric(base_w, gnn_w, 
                      "Total Waiting Time", "Accumulated Seconds", 
                      "benchmark_wait.png", "#2980b9", higher_is_better=False)

    # NEW: Average Speed Plot
    plot_single_metric(base_s, gnn_s, 
                      "Average Travel Speed (Proxy for Travel Time)", "Speed (m/s)", 
                      "benchmark_speed.png", "#e67e22", higher_is_better=True) # Orange

    plot_single_metric(base_c, gnn_c, 
                      "Total Performance (Weighted Cost)", "Weighted Cost", 
                      "benchmark_cost.png", "#8e44ad", higher_is_better=False)

    # --- 2. Save Combined Summary Plot (4 Subplots) ---
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 18), sharex=True)
    
    # Subplot 1: Queue
    ax1.plot(x, base_q, label='Baseline', color='#7f8c8d', linestyle='--', linewidth=1.5)
    ax1.plot(x, gnn_q, label='GNN Model', color='#27ae60', linewidth=2)
    ax1.fill_between(x, gnn_q, alpha=0.1, color='#27ae60')
    ax1.set_title('Metric 1: Network Congestion (Queue)', fontweight='bold')
    ax1.set_ylabel('Vehicles')
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)

    # Subplot 2: Wait
    ax2.plot(x, base_w, label='Baseline', color='#7f8c8d', linestyle='--', linewidth=1.5)
    ax2.plot(x, gnn_w, label='GNN Model', color='#2980b9', linewidth=2)
    ax2.fill_between(x, gnn_w, alpha=0.1, color='#2980b9')
    ax2.set_title('Metric 2: Total Waiting Time', fontweight='bold')
    ax2.set_ylabel('Seconds')
    ax2.legend(loc='upper left')
    ax2.grid(True, alpha=0.3)

    # Subplot 3: Speed (Travel Time)
    ax3.plot(x, base_s, label='Baseline', color='#7f8c8d', linestyle='--', linewidth=1.5)
    ax3.plot(x, gnn_s, label='GNN Model', color='#e67e22', linewidth=2)
    ax3.fill_between(x, gnn_s, alpha=0.1, color='#e67e22')
    ax3.set_title('Metric 3: Avg Travel Speed (Higher = Less Travel Time)', fontweight='bold')
    ax3.set_ylabel('Speed (m/s)')
    ax3.legend(loc='lower right')
    ax3.grid(True, alpha=0.3)

    # Subplot 4: Cost
    ax4.plot(x, base_c, label='Baseline', color='#7f8c8d', linestyle='--', linewidth=1.5)
    ax4.plot(x, gnn_c, label='GNN Performance', color='#8e44ad', linewidth=2)
    ax4.fill_between(x, gnn_c, alpha=0.1, color='#8e44ad')
    ax4.set_title('Metric 4: Total Performance (Weighted Cost)', fontweight='bold')
    ax4.set_ylabel('Cost')
    ax4.set_xlabel('Simulation Steps')
    ax4.legend(loc='upper left')
    ax4.grid(True, alpha=0.3)

    # Add Summary Text
    # Cost Improvement (Lower is better)
    imp_c = ((np.mean(base_c) - np.mean(gnn_c)) / np.mean(base_c)) * 100
    # Speed Improvement (Higher is better)
    imp_s = ((np.mean(gnn_s) - np.mean(base_s)) / np.mean(base_s)) * 100

    summary_text = (
        f"Overall Performance Improvement: {imp_c:.2f}% (Cost Reduction)\n"
        f"Travel Time Efficiency: {imp_s:.2f}% (Speed Increase)"
    )
    
    plt.figtext(0.5, 0.02, summary_text, 
                ha="center", fontsize=14, bbox={"facecolor":"white", "alpha":0.8, "pad":5})

    plt.tight_layout(rect=[0, 0.06, 1, 1])
    save_path = f"{PLOT_DIR}/benchmark_summary.png"
    plt.savefig(save_path, dpi=300)
    plt.close()
    print(f"   Saved: {save_path}")

def main():
    print("="*40)
    print("  TRAFFIC OPTIMIZATION BENCHMARK")
    print("="*40)

    # 1. Run Simulations
    base_data = run_simulation(mode="baseline")
    gnn_data = run_simulation(mode="gnn")

    if len(gnn_data[0]) == 0:
        print("GNN Simulation failed. Exiting.")
        return

    # Unpack
    base_q, base_w, base_s, base_c = base_data
    gnn_q, gnn_w, gnn_s, gnn_c = gnn_data

    # 2. Calculate Averages
    avg_base_cost = np.mean(base_c)
    avg_gnn_cost = np.mean(gnn_c)
    
    avg_base_speed = np.mean(base_s)
    avg_gnn_speed = np.mean(gnn_s)

    # 3. Calculate Improvement %
    # Cost: Lower is Better -> (Base - GNN) / Base
    imp_cost = ((avg_base_cost - avg_gnn_cost) / avg_base_cost) * 100
    
    # Speed: Higher is Better -> (GNN - Base) / Base
    imp_speed = ((avg_gnn_speed - avg_base_speed) / avg_base_speed) * 100

    print("\n" + "-"*40)
    print("RESULTS SUMMARY")
    print("-"*40)
    print(f"{'Metric':<25} | {'Baseline':<10} | {'GNN Model':<10} | {'Improvement':<10}")
    print("-" * 65)
    print(f"{'Avg Weighted Cost':<25} | {avg_base_cost:<10.2f} | {avg_gnn_cost:<10.2f} | {imp_cost:+.2f}%")
    print(f"{'Avg Network Speed (m/s)':<25} | {avg_base_speed:<10.2f} | {avg_gnn_speed:<10.2f} | {imp_speed:+.2f}%")
    print("-" * 65)

    # 4. Save Plots
    save_all_plots(base_data, gnn_data)

if __name__ == "__main__":
    main()