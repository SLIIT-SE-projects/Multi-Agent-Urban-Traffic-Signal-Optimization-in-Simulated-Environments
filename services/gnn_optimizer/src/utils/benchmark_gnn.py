import os
import sys
import time
import torch
import numpy as np
import matplotlib.pyplot as plt

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.graphBuilder.sumo_manager import SumoManager
from src.graphBuilder.graph_builder import TrafficGraphBuilder
from src.models.hgat_core import RecurrentHGAT
from src.config import SimConfig, GraphConfig, TrainConfig, ModelConfig
from src.training.marl_finetune_actor_critic import apply_actions_unified

STEPS = 1000
MODEL_PATH = "experiments/saved_models/final_marl_model_best.pth"
PLOT_DIR = "experiments/plots"
plt.style.use('bmh')


# ═══════════════════════════════════════════════════════
# PAPER EVALUATOR — Embedded directly, no separate file needed
# ═══════════════════════════════════════════════════════
class PaperEvaluator:
    """Tracks all metrics needed to reproduce paper-style evaluation figures."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.queue_lengths = []       # Per-step network queue
        self.waiting_times = []       # Per-step total wait
        self.avg_speeds = []          # Per-step avg speed
        self.halting_vehicles = []    # Per-step halting count
        self.delays = []              # Per-step normalized delay
        self.decision_latencies_ms = []  # Per-decision inference time (ms)
        self.vehicle_travel_times = {}   # vehicle_id -> (depart_time, arrive_time)
        self.vehicle_depart_times = {}   # vehicle_id -> depart_time

    def record_step(self, snapshot):
        """Call every simulation step."""
        total_queue = 0
        total_wait = 0
        total_speed = 0
        total_halting = 0
        total_delay = 0
        num_lanes = 0

        for lane_id, info in snapshot['lanes'].items():
            q = info.get('queue_length', 0)
            w = info.get('waiting_time', 0)
            s = info.get('avg_speed', 0)

            total_queue += q
            total_wait += w
            total_speed += s
            total_halting += q  # halting = queued vehicles

            # Delay = (v_max - v_avg) / v_max, normalized
            v_max = 13.89
            delay = max(0, (v_max - s) / v_max) if v_max > 0 else 0
            total_delay += delay
            num_lanes += 1

        self.queue_lengths.append(total_queue)
        self.waiting_times.append(total_wait)
        self.avg_speeds.append(total_speed / num_lanes if num_lanes > 0 else 0)
        self.halting_vehicles.append(total_halting)
        self.delays.append(total_delay / num_lanes if num_lanes > 0 else 0)

    def record_decision_time(self, t_start, t_end):
        """Call after each model inference. Times in seconds."""
        self.decision_latencies_ms.append((t_end - t_start) * 1000.0)

    def get_summary(self):
        """Returns dict of aggregate metrics."""
        lats = self.decision_latencies_ms
        return {
            'avg_queue_length':       np.mean(self.queue_lengths),
            'avg_waiting_time':       np.mean(self.waiting_times),
            'avg_speed':              np.mean(self.avg_speeds),
            'avg_delay':              np.mean(self.delays),
            'avg_halting_vehicles':   np.mean(self.halting_vehicles),
            'avg_decision_latency_ms': np.mean(lats) if lats else 0.0,
            'p99_decision_latency_ms': np.percentile(lats, 99) if lats else 0.0,
        }

    def plot_paper_figures(self, baseline_eval, gnn_eval, save_dir):
        """Generate all paper-style comparison figures."""
        os.makedirs(save_dir, exist_ok=True)
        x = range(len(baseline_eval.queue_lengths))

        # ── Figure 1: Speed over time (Paper Fig 11 equivalent) ──────────
        plt.figure(figsize=(10, 5))
        plt.plot(x, baseline_eval.avg_speeds, '--', color='gray',
                 label='Baseline', linewidth=1.5)
        plt.plot(x, gnn_eval.avg_speeds, color='#e67e22',
                 label='GNN-PPO', linewidth=2)
        plt.title('Average Speed Over Time', fontsize=14, fontweight='bold')
        plt.xlabel('Simulation Steps')
        plt.ylabel('Speed (m/s)')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_speed.png", dpi=300)
        plt.close()

        # ── Figure 2: Queue length over time (Paper Fig 13 equivalent) ───
        plt.figure(figsize=(10, 5))
        plt.plot(x, baseline_eval.queue_lengths, '--', color='gray',
                 label='Baseline', linewidth=1.5)
        plt.plot(x, gnn_eval.queue_lengths, color='#27ae60',
                 label='GNN-PPO', linewidth=2)
        plt.fill_between(x, gnn_eval.queue_lengths, alpha=0.1, color='#27ae60')
        plt.title('Queue Length Over Time', fontsize=14, fontweight='bold')
        plt.xlabel('Simulation Steps')
        plt.ylabel('Vehicles in Queue')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_queue.png", dpi=300)
        plt.close()

        # ── Figure 3: Waiting time over time (Paper Fig equivalent) ──────
        plt.figure(figsize=(10, 5))
        plt.plot(x, baseline_eval.waiting_times, '--', color='gray',
                 label='Baseline', linewidth=1.5)
        plt.plot(x, gnn_eval.waiting_times, color='#2980b9',
                 label='GNN-PPO', linewidth=2)
        plt.title('Total Waiting Time Over Time', fontsize=14, fontweight='bold')
        plt.xlabel('Simulation Steps')
        plt.ylabel('Seconds')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_wait.png", dpi=300)
        plt.close()

        # ── Figure 4: Running vs Halting (Paper Fig 14 equivalent) ───────
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
        ax1.plot(x, baseline_eval.halting_vehicles, '--', color='gray',
                 label='Halting', linewidth=1.5)
        ax1.set_title('Baseline: Halting Vehicles', fontweight='bold')
        ax1.set_xlabel('Steps')
        ax1.set_ylabel('Vehicles')
        ax1.grid(True, alpha=0.3)

        ax2.plot(x, gnn_eval.halting_vehicles, color='#8e44ad',
                 label='Halting', linewidth=2)
        ax2.set_title('GNN-PPO: Halting Vehicles', fontweight='bold')
        ax2.set_xlabel('Steps')
        ax2.grid(True, alpha=0.3)
        plt.suptitle('Halting Vehicle Comparison', fontsize=13, fontweight='bold')
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_halting.png", dpi=300)
        plt.close()

        # ── Figure 5: Queue box plot (Paper Fig 17 equivalent) ────────────
        plt.figure(figsize=(8, 6))
        plt.boxplot(
            [baseline_eval.queue_lengths, gnn_eval.queue_lengths],
            labels=['Baseline', 'GNN-PPO'],
            patch_artist=True,
            boxprops=dict(facecolor='#3498db', alpha=0.6)
        )
        plt.title('Queue Length Distribution', fontsize=14, fontweight='bold')
        plt.ylabel('Vehicles in Queue')
        plt.grid(True, alpha=0.3)
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_boxplot.png", dpi=300)
        plt.close()

        # ── Figure 6: Decision latency (Unique metric) ────────────────────
        if gnn_eval.decision_latencies_ms:
            plt.figure(figsize=(8, 5))
            plt.hist(gnn_eval.decision_latencies_ms, bins=40,
                     color='#e74c3c', alpha=0.7, edgecolor='black')
            p50 = np.percentile(gnn_eval.decision_latencies_ms, 50)
            p99 = np.percentile(gnn_eval.decision_latencies_ms, 99)
            plt.axvline(p50, color='blue', linestyle='--',
                        label=f'P50: {p50:.2f}ms')
            plt.axvline(p99, color='red', linestyle='--',
                        label=f'P99: {p99:.2f}ms')
            plt.title('GNN Inference Latency Distribution',
                      fontsize=14, fontweight='bold')
            plt.xlabel('Latency (ms)')
            plt.ylabel('Frequency')
            plt.legend()
            plt.tight_layout()
            plt.savefig(f"{save_dir}/paper_fig_latency.png", dpi=300)
            plt.close()

        # ── Figure 7: Improvement summary table ───────────────────────────
        base_s = baseline_eval.get_summary()
        gnn_s = gnn_eval.get_summary()

        metrics = [
            ('Avg Queue (veh)',    'avg_queue_length',     True),
            ('Avg Wait (s)',       'avg_waiting_time',     True),
            ('Avg Speed (m/s)',    'avg_speed',            False),
            ('Avg Delay',         'avg_delay',            True),
            ('Avg Halting',       'avg_halting_vehicles', True),
        ]

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.axis('off')
        table_data = [['Metric', 'Baseline', 'GNN-PPO', 'Improvement']]
        for label, key, lower_better in metrics:
            b = base_s.get(key, 0)
            g = gnn_s.get(key, 0)
            imp = ((b - g) / b * 100) if lower_better and b != 0 \
                  else ((g - b) / b * 100) if b != 0 else 0
            arrow = '▼' if (imp > 0 and lower_better) else '▲'
            table_data.append([label, f'{b:.2f}', f'{g:.2f}',
                                f'{arrow} {abs(imp):.1f}%'])

        # Latency row (GNN only)
        table_data.append(['Inference P99 (ms)', 'N/A',
                            f"{gnn_s.get('p99_decision_latency_ms', 0):.2f}", ''])

        table = ax.table(cellText=table_data[1:],
                         colLabels=table_data[0],
                         loc='center', cellLoc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1.2, 1.8)

        # Color improvement cells
        for i in range(1, len(table_data)):
            imp_str = table_data[i][3]
            if '▼' in imp_str:
                table[i, 3].set_facecolor('#d5f5e3')  # green = improved
            elif '▲' in imp_str and table_data[i][0] == 'Avg Speed (m/s)':
                table[i, 3].set_facecolor('#d5f5e3')

        plt.title('Performance Summary vs Baseline',
                  fontsize=14, fontweight='bold', pad=20)
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_table_summary.png", dpi=300,
                    bbox_inches='tight')
        plt.close()

        print(f"[PaperEvaluator] All figures saved to {save_dir}/")


# ═══════════════════════════════════════════════════════
# MAIN BENCHMARK LOGIC
# ═══════════════════════════════════════════════════════

def calculate_weighted_cost(queue, wait):
    return (TrainConfig.W_QUEUE * queue) + (TrainConfig.W_WAIT * wait)

def get_metrics(snapshot):
    total_queue, total_wait, total_speed, num_lanes = 0, 0, 0, 0
    for lane_id, info in snapshot['lanes'].items():
        total_queue += info['queue_length']
        total_wait += info['waiting_time']
        total_speed += info.get('avg_speed', 0)
        num_lanes += 1
    cost = calculate_weighted_cost(total_queue, total_wait)
    avg_speed = total_speed / num_lanes if num_lanes > 0 else 0
    return total_queue, total_wait, avg_speed, cost


def run_simulation(mode="baseline"):
    label = "Baseline" if mode == "baseline" else "GNN Model"
    print(f"\n[{label}] Starting simulation...")

    hard_route = "simulation/routes_hard.xml"
    active_route = "simulation/routes.rou.xml"
    if os.path.exists(hard_route):
        import shutil
        shutil.copy(hard_route, active_route)

    manager = SumoManager(SimConfig.SUMO_CFG, use_gui=False)
    graph_builder = TrafficGraphBuilder(SimConfig.NET_FILE)
    manager.start()
    manager.step()

    # ── Create one PaperEvaluator per run ─────────────────────────────────
    evaluator = PaperEvaluator()

    model = None
    hidden_state = None
    queues, waits, speeds, costs = [], [], [], []
    idx_to_id = {v: k for k, v in graph_builder.tls_map.items()}
    ACTION_INTERVAL = 20

    if mode == "gnn":
        snapshot = manager.get_snapshot()
        data = graph_builder.create_hetero_data(snapshot)
        model = RecurrentHGAT(
            hidden_channels=TrainConfig.HIDDEN_DIM,
            out_channels=GraphConfig.NUM_ACTIONS,
            num_heads=ModelConfig.NUM_HEADS,
            metadata=data.metadata()
        )
        try:
            model.load_state_dict(torch.load(MODEL_PATH, map_location='cpu'))
            model.eval()
            print(f"   Loaded: {MODEL_PATH}")
        except Exception as e:
            print(f"   Load failed: {e}")
            manager.close()
            return None

    for t in range(STEPS):

        if mode == "gnn" and t % ACTION_INTERVAL == 0:
            snapshot = manager.get_snapshot()
            data = graph_builder.create_hetero_data(snapshot)

            # ── Time the inference ─────────────────────────────────────────
            t_start = time.perf_counter()
            with torch.no_grad():
                out = model(data.x_dict, data.edge_index_dict,
                            hidden_state, data.edge_attr_dict)
                logits = out[0]
                hidden_state = out[-1]
                actions = torch.argmax(logits, dim=1)
            t_end = time.perf_counter()

            # ── Record decision time ───────────────────────────────────────
            evaluator.record_decision_time(t_start, t_end)

            apply_actions_unified(actions, snapshot, idx_to_id, manager)

        manager.step()
        snap = manager.get_snapshot()

        # ── Record metrics every step ──────────────────────────────────────
        evaluator.record_step(snap)

        q, w, s, c = get_metrics(snap)
        queues.append(q)
        waits.append(w)
        speeds.append(s)
        costs.append(c)

        if t % 200 == 0:
            print(f"   Step {t}: Queue={q:.1f} | Speed={s:.2f} m/s")

    manager.close()

    # Attach raw arrays to evaluator for legacy plot compatibility
    evaluator.raw_queues = np.array(queues)
    evaluator.raw_waits  = np.array(waits)
    evaluator.raw_speeds = np.array(speeds)
    evaluator.raw_costs  = np.array(costs)

    return evaluator


def save_benchmark_plots(base_eval, gnn_eval):
    os.makedirs(PLOT_DIR, exist_ok=True)
    x = range(STEPS)

    base_q = base_eval.raw_queues
    base_w = base_eval.raw_waits
    base_s = base_eval.raw_speeds
    base_c = base_eval.raw_costs
    gnn_q  = gnn_eval.raw_queues
    gnn_w  = gnn_eval.raw_waits
    gnn_s  = gnn_eval.raw_speeds
    gnn_c  = gnn_eval.raw_costs

    imp_c = ((np.mean(base_c) - np.mean(gnn_c)) / np.mean(base_c)) * 100
    imp_s = ((np.mean(gnn_s) - np.mean(base_s)) / np.mean(base_s)) * 100

    fig, axes = plt.subplots(4, 1, figsize=(12, 18), sharex=True)
    titles = ['Metric 1: Network Congestion (Queue)',
              'Metric 2: Total Waiting Time',
              'Metric 3: Avg Travel Speed (Higher = Less Travel Time)',
              'Metric 4: Total Performance (Weighted Cost)']
    ylabels = ['Vehicles', 'Seconds', 'Speed (m/s)', 'Cost']
    colors  = ['#27ae60', '#2980b9', '#e67e22', '#8e44ad']
    gnn_arrs = [gnn_q, gnn_w, gnn_s, gnn_c]
    base_arrs = [base_q, base_w, base_s, base_c]
    locs = ['upper left', 'upper left', 'lower right', 'upper left']

    for ax, title, ylabel, color, ga, ba, loc in zip(
            axes, titles, ylabels, colors, gnn_arrs, base_arrs, locs):
        ax.plot(x, ba, '--', color='#7f8c8d', label='Baseline', linewidth=1.5)
        ax.plot(x, ga, color=color, label='GNN Model', linewidth=2)
        ax.fill_between(x, ga, alpha=0.1, color=color)
        ax.set_title(title, fontweight='bold')
        ax.set_ylabel(ylabel)
        ax.legend(loc=loc)
        ax.grid(True, alpha=0.3)

    axes[-1].set_xlabel('Simulation Steps')
    summary = (f"Overall Performance Improvement: {imp_c:.2f}% (Cost Reduction)\n"
               f"Travel Time Efficiency: {imp_s:.2f}% (Speed Increase)")
    plt.figtext(0.5, 0.01, summary, ha='center', fontsize=13,
                bbox=dict(facecolor='white', alpha=0.8, pad=5))
    plt.tight_layout(rect=[0, 0.05, 1, 1])
    plt.savefig(f"{PLOT_DIR}/benchmark_summary.png", dpi=300)
    plt.close()
    print(f"   Saved: benchmark_summary.png")


def main():
    print("=" * 50)
    print("  TRAFFIC OPTIMIZATION BENCHMARK")
    print("=" * 50)

    baseline_eval = run_simulation(mode="baseline")
    gnn_eval      = run_simulation(mode="gnn")

    if gnn_eval is None:
        print("GNN simulation failed.")
        return

    # ── Print terminal summary ─────────────────────────────────────────────
    base_s = baseline_eval.get_summary()
    gnn_s  = gnn_eval.get_summary()

    print("\n" + "=" * 65)
    print("RESULTS SUMMARY")
    print("=" * 65)
    rows = [
        ('Avg Queue (veh)',       'avg_queue_length',       True),
        ('Avg Wait (s)',          'avg_waiting_time',       True),
        ('Avg Speed (m/s)',       'avg_speed',              False),
        ('Avg Delay',             'avg_delay',              True),
        ('Avg Halting',          'avg_halting_vehicles',   True),
        ('Inference P99 (ms)',   'p99_decision_latency_ms', False),
    ]
    print(f"{'Metric':<25} | {'Baseline':>10} | {'GNN-PPO':>10} | {'Improve':>10}")
    print("-" * 65)
    for label, key, lower_better in rows:
        b = base_s.get(key, 0)
        g = gnn_s.get(key, 0)
        if b != 0:
            imp = ((b - g) / b * 100) if lower_better else ((g - b) / b * 100)
        else:
            imp = 0
        tick = '✅' if imp > 0 else ('➖' if imp == 0 else '❌')
        print(f"{label:<25} | {b:>10.3f} | {g:>10.3f} | {imp:>+9.2f}% {tick}")
    print("=" * 65)

    # ── Generate all plots ─────────────────────────────────────────────────
    print("\n[Plotting] Generating benchmark plots...")
    save_benchmark_plots(baseline_eval, gnn_eval)

    print("\n[Plotting] Generating paper-style figures...")
    gnn_eval.plot_paper_figures(baseline_eval, gnn_eval, PLOT_DIR)

    print(f"\n✅ All plots saved to: {PLOT_DIR}/")


if __name__ == "__main__":
    main()
