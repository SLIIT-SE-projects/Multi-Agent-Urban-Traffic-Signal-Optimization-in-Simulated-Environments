# src/utils/paper_evaluator.py
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import time
import os


class PaperEvaluator:
    """
    Implements ALL evaluation metrics from the HGAT-MARL paper
    plus additional metrics for your research paper.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        # Per-step metrics
        self.queue_lengths = []       # Avg queue length per step (paper Fig 13)
        self.waiting_times = []       # Avg waiting time per step
        self.avg_speeds = []          # Avg speed per step (paper Fig 11)
        self.delays = []              # Delay metric (paper Eq. 14)
        self.running_counts = []      # Vehicles running (paper Fig 14)
        self.halting_counts = []      # Vehicles halting (paper Fig 14)

        # Per-vehicle metrics (requires traci vehicle tracking)
        self.vehicle_travel_times = {}   # vehicle_id -> travel_time
        self.vehicle_depart_times = {}   # vehicle_id -> depart_time
        self.vehicle_arrive_times = {}   # vehicle_id -> arrive_time
        self.vehicle_depart_delays = {}  # vehicle_id -> depart_delay

        # Decision timing (your unique metric)
        self.decision_latencies_ms = []

        # Episode-level
        self.completed_trips = []

    def record_step(self, snapshot, traci_conn=None):
        """Call this every simulation step."""
        lanes = snapshot['lanes']

        # Queue and Wait
        queues = [info['queue_length'] for info in lanes.values()]
        waits = [info['waiting_time'] for info in lanes.values()]
        speeds = [info['avg_speed'] for info in lanes.values()]

        self.queue_lengths.append(np.mean(queues))
        self.waiting_times.append(np.mean(waits))
        self.avg_speeds.append(np.mean(speeds))

        # Delay (paper Eq. 14): (vmax - v) / vmax
        MAX_SPEED = 13.89
        delay = np.mean([(MAX_SPEED - s) / MAX_SPEED for s in speeds])
        self.delays.append(delay)

        # Running vs Halting (requires traci)
        if traci_conn is not None:
            try:
                vehicle_ids = traci_conn.vehicle.getIDList()
                halting = sum(
                    1 for v in vehicle_ids
                    if traci_conn.vehicle.getSpeed(v) < 0.1
                )
                running = len(vehicle_ids) - halting
                self.running_counts.append(running)
                self.halting_counts.append(halting)

                # Track individual vehicle departure times
                for v_id in vehicle_ids:
                    if v_id not in self.vehicle_depart_times:
                        self.vehicle_depart_times[v_id] = traci_conn.vehicle.getDeparture(v_id)
                        self.vehicle_depart_delays[v_id] = traci_conn.vehicle.getDepartDelay(v_id)

            except Exception:
                pass

    def record_decision_time(self, inference_start: float, inference_end: float):
        """Record how long the model took to make a decision."""
        latency_ms = (inference_end - inference_start) * 1000.0
        self.decision_latencies_ms.append(latency_ms)

    def record_vehicle_arrival(self, vehicle_id, arrive_time):
        """Call when a vehicle completes its trip."""
        if vehicle_id in self.vehicle_depart_times:
            travel_time = arrive_time - self.vehicle_depart_times[vehicle_id]
            self.vehicle_travel_times[vehicle_id] = travel_time
            self.vehicle_arrive_times[vehicle_id] = arrive_time

    def get_summary(self):
        """Returns all aggregate metrics for comparison table."""
        travel_times = list(self.vehicle_travel_times.values())
        depart_delays = list(self.vehicle_depart_delays.values())

        summary = {
            # Paper Table III equivalent metrics
            'avg_travel_time': np.mean(travel_times) if travel_times else 0,
            'avg_waiting_time': np.mean(self.waiting_times) if self.waiting_times else 0,
            'avg_queue_length': np.mean(self.queue_lengths) if self.queue_lengths else 0,
            'avg_delay': np.mean(self.delays) if self.delays else 0,
            'avg_speed': np.mean(self.avg_speeds) if self.avg_speeds else 0,

            # Stop count proxy (fraction of time halting)
            'avg_halting_vehicles': np.mean(self.halting_counts) if self.halting_counts else 0,

            # Your unique metric
            'avg_decision_latency_ms': np.mean(self.decision_latencies_ms) if self.decision_latencies_ms else 0,
            'max_decision_latency_ms': np.max(self.decision_latencies_ms) if self.decision_latencies_ms else 0,
            'p99_decision_latency_ms': np.percentile(self.decision_latencies_ms, 99) if self.decision_latencies_ms else 0,

            # Departure delay
            'avg_depart_delay': np.mean(depart_delays) if depart_delays else 0,
        }
        return summary

    def plot_paper_figures(self, baseline_eval, gnn_eval, save_dir):
        """
        Generates all figures matching the paper's style.
        baseline_eval and gnn_eval are PaperEvaluator instances.
        """
        os.makedirs(save_dir, exist_ok=True)

        # --- Figure 1: Speed curves over time (paper Fig 11 equivalent) ---
        self._plot_speed_comparison(baseline_eval, gnn_eval, save_dir)

        # --- Figure 2: Queue length over time (paper Fig 13 equivalent) ---
        self._plot_queue_comparison(baseline_eval, gnn_eval, save_dir)

        # --- Figure 3: Running vs Halting (paper Fig 14 equivalent) ---
        self._plot_running_halting(baseline_eval, gnn_eval, save_dir)

        # --- Figure 4: Travel time bar chart (paper Fig 15 equivalent) ---
        self._plot_travel_time_bar(baseline_eval, gnn_eval, save_dir)

        # --- Figure 5: Departure/Arrival delay scatter (paper Fig 12 equiv) ---
        self._plot_delay_scatter(baseline_eval, gnn_eval, save_dir)

        # --- Figure 6: Queue length box plot (paper Fig 17 equivalent) ---
        self._plot_queue_boxplot(baseline_eval, gnn_eval, save_dir)

        # --- Figure 7: YOUR UNIQUE — Decision Latency Distribution ---
        self._plot_decision_latency(gnn_eval, save_dir)

        # --- Figure 8: YOUR UNIQUE — Improvement Summary Table ---
        self._plot_improvement_table(baseline_eval, gnn_eval, save_dir)

    def _plot_speed_comparison(self, baseline, gnn, save_dir):
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        steps = range(len(baseline.avg_speeds))

        axes[0].plot(steps, baseline.avg_speeds, color='#2980b9', linewidth=1)
        axes[0].set_title('Baseline: Avg Speed per Lane', fontweight='bold')
        axes[0].set_xlabel('Simulation Step')
        axes[0].set_ylabel('Speed (m/s)')
        axes[0].set_ylim(0, 15)

        axes[1].plot(range(len(gnn.avg_speeds)), gnn.avg_speeds,
                     color='#e74c3c', linewidth=1)
        axes[1].set_title('GNN Model: Avg Speed per Lane', fontweight='bold')
        axes[1].set_xlabel('Simulation Step')
        axes[1].set_ylabel('Speed (m/s)')
        axes[1].set_ylim(0, 15)

        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_speed_comparison.png", dpi=300)
        plt.close()

    def _plot_queue_comparison(self, baseline, gnn, save_dir):
        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        axes[0].plot(range(len(baseline.queue_lengths)),
                     baseline.queue_lengths, color='#7f8c8d', linewidth=1)
        axes[0].set_title('Baseline: Queue Length Over Time', fontweight='bold')
        axes[0].set_xlabel('Simulation Time (steps)')
        axes[0].set_ylabel('Queue Length (vehicles)')

        axes[1].plot(range(len(gnn.queue_lengths)),
                     gnn.queue_lengths, color='#27ae60', linewidth=1)
        axes[1].set_title('GNN Model: Queue Length Over Time', fontweight='bold')
        axes[1].set_xlabel('Simulation Time (steps)')
        axes[1].set_ylabel('Queue Length (vehicles)')

        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_queue_comparison.png", dpi=300)
        plt.close()

    def _plot_running_halting(self, baseline, gnn, save_dir):
        if not baseline.running_counts:
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))
        steps_b = range(len(baseline.running_counts))
        steps_g = range(len(gnn.running_counts))

        axes[0].fill_between(steps_b, baseline.running_counts,
                              alpha=0.7, color='#3498db', label='Running')
        axes[0].fill_between(steps_b, baseline.halting_counts,
                              alpha=0.7, color='#e67e22', label='Halting')
        axes[0].set_title('Baseline: Running vs Halting', fontweight='bold')
        axes[0].legend()

        axes[1].fill_between(steps_g, gnn.running_counts,
                              alpha=0.7, color='#3498db', label='Running')
        axes[1].fill_between(steps_g, gnn.halting_counts,
                              alpha=0.7, color='#e67e22', label='Halting')
        axes[1].set_title('GNN Model: Running vs Halting', fontweight='bold')
        axes[1].legend()

        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_running_halting.png", dpi=300)
        plt.close()

    def _plot_travel_time_bar(self, baseline, gnn, save_dir):
        base_summary = baseline.get_summary()
        gnn_summary = gnn.get_summary()

        labels = ['Baseline', 'GNN Model']
        values = [base_summary['avg_travel_time'], gnn_summary['avg_travel_time']]
        colors = ['#95a5a6', '#e74c3c']

        fig, ax = plt.subplots(figsize=(6, 7))
        bars = ax.bar(labels, values, color=colors, width=0.4, edgecolor='black')

        for bar, val in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 5, f'{val:.1f}s',
                    ha='center', fontweight='bold')

        improvement = ((values[0] - values[1]) / values[0]) * 100
        ax.set_title(f'Average Travel Time\n(Improvement: {improvement:.1f}%)',
                     fontweight='bold')
        ax.set_ylabel('Travel Time (seconds)')
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_travel_time_bar.png", dpi=300)
        plt.close()

    def _plot_delay_scatter(self, baseline, gnn, save_dir):
        """Departure vs Arrival delay scatter (paper Fig 12 style)."""
        fig, axes = plt.subplots(1, 2, figsize=(14, 6))

        for ax, evaluator, title in [
            (axes[0], baseline, 'Baseline'),
            (axes[1], gnn, 'GNN Model')
        ]:
            if evaluator.vehicle_depart_times and evaluator.vehicle_arrive_times:
                common = set(evaluator.vehicle_depart_times.keys()) & \
                         set(evaluator.vehicle_arrive_times.keys())
                departs = [evaluator.vehicle_depart_times[v] for v in common]
                arrives = [evaluator.vehicle_arrive_times[v] for v in common]

                ax.scatter(departs, arrives, alpha=0.3, s=5, c='#3498db')
                max_val = max(max(departs), max(arrives))
                ax.plot([0, max_val], [0, max_val], 'r--',
                        linewidth=1, label='y=x (instant travel)')
                ax.legend()

            ax.set_title(f'{title}: Departure vs Arrival Time', fontweight='bold')
            ax.set_xlabel('Departure Time (s)')
            ax.set_ylabel('Arrival Time (s)')

        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_departure_arrival.png", dpi=300)
        plt.close()

    def _plot_queue_boxplot(self, baseline, gnn, save_dir):
        """Box plot comparison (paper Fig 17 style)."""
        fig, ax = plt.subplots(figsize=(6, 7))

        data = [baseline.queue_lengths, gnn.queue_lengths]
        bp = ax.boxplot(data, labels=['Baseline', 'GNN Model'],
                        patch_artist=True, notch=False)

        colors = ['#95a5a6', '#27ae60']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

        ax.set_title('Queue Length Distribution\n(Box Plot Comparison)',
                     fontweight='bold')
        ax.set_ylabel('Queue Length (vehicles)')
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_queue_boxplot.png", dpi=300)
        plt.close()

    def _plot_decision_latency(self, gnn, save_dir):
        """YOUR UNIQUE METRIC: How fast does the model think?"""
        if not gnn.decision_latencies_ms:
            return

        fig, axes = plt.subplots(1, 2, figsize=(14, 5))

        # Timeline
        axes[0].plot(gnn.decision_latencies_ms, color='#8e44ad', linewidth=1)
        axes[0].axhline(y=np.mean(gnn.decision_latencies_ms),
                        color='red', linestyle='--',
                        label=f"Mean: {np.mean(gnn.decision_latencies_ms):.2f}ms")
        axes[0].axhline(y=np.percentile(gnn.decision_latencies_ms, 99),
                        color='orange', linestyle=':',
                        label=f"P99: {np.percentile(gnn.decision_latencies_ms, 99):.2f}ms")
        axes[0].set_title('Decision Latency Over Simulation', fontweight='bold')
        axes[0].set_xlabel('Decision Number')
        axes[0].set_ylabel('Latency (ms)')
        axes[0].legend()

        # Histogram
        axes[1].hist(gnn.decision_latencies_ms, bins=50,
                     color='#8e44ad', edgecolor='white', alpha=0.8)
        axes[1].set_title('Decision Latency Distribution', fontweight='bold')
        axes[1].set_xlabel('Latency (ms)')
        axes[1].set_ylabel('Frequency')

        plt.suptitle('Model Decision Thinking Time Analysis', fontsize=14,
                     fontweight='bold')
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_decision_latency.png", dpi=300)
        plt.close()

    def _plot_improvement_table(self, baseline, gnn, save_dir):
        """Visual comparison table matching paper Table III."""
        base_s = baseline.get_summary()
        gnn_s = gnn.get_summary()

        metrics = [
            ('Travel Time (s)', 'avg_travel_time', True),
            ('Waiting Time (s)', 'avg_waiting_time', True),
            ('Queue Length (veh)', 'avg_queue_length', True),
            ('Delay', 'avg_delay', True),
            ('Avg Speed (m/s)', 'avg_speed', False),
            ('Halting Vehicles', 'avg_halting_vehicles', True),
            ('Decision Latency (ms)', 'avg_decision_latency_ms', False),
        ]

        fig, ax = plt.subplots(figsize=(12, 5))
        ax.axis('off')

        table_data = []
        col_colors = []

        for label, key, lower_is_better in metrics:
            base_val = base_s.get(key, 0)
            gnn_val = gnn_s.get(key, 0)

            if base_val != 0:
                if lower_is_better:
                    improvement = ((base_val - gnn_val) / base_val) * 100
                else:
                    improvement = ((gnn_val - base_val) / base_val) * 100
            else:
                improvement = 0

            color = '#2ecc71' if improvement > 0 else '#e74c3c'
            table_data.append([
                label,
                f'{base_val:.2f}',
                f'{gnn_val:.2f}',
                f'{improvement:+.2f}%'
            ])
            col_colors.append(['white', 'white', 'white', color])

        table = ax.table(
            cellText=table_data,
            colLabels=['Metric', 'Baseline', 'GNN Model', 'Improvement'],
            cellLoc='center',
            loc='center',
            cellColours=col_colors
        )
        table.auto_set_font_size(False)
        table.set_fontsize(11)
        table.scale(1, 2)

        ax.set_title('Performance Comparison Summary',
                     fontsize=14, fontweight='bold', pad=20)
        plt.tight_layout()
        plt.savefig(f"{save_dir}/paper_fig_summary_table.png", dpi=300, bbox_inches='tight')
        plt.close()
        print("\nSummary Table:")
        print(f"{'Metric':<25} | {'Baseline':>10} | {'GNN':>10} | {'Improvement':>12}")
        print("-" * 65)
        for row in table_data:
            print(f"{row[0]:<25} | {row[1]:>10} | {row[2]:>10} | {row[3]:>12}")