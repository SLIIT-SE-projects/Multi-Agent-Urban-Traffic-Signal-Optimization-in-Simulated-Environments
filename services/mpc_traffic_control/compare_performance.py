import pandas as pd
import matplotlib.pyplot as plt
import os

BASELINE_PATH = "data/logs/baseline/simulation_data.csv"
MPC_PATH = "data/logs/mpc/simulation_data.csv"

def compare():
    if not os.path.exists(BASELINE_PATH) or not os.path.exists(MPC_PATH):
        print("Error: Log files not found. Run both Baseline and MPC modes first.")
        return

    print("Loading data...")
    df_base = pd.read_csv(BASELINE_PATH)
    df_mpc = pd.read_csv(MPC_PATH)

    # Trim to shortest length to align
    min_len = min(len(df_base), len(df_mpc))
    df_base = df_base.iloc[:min_len]
    df_mpc = df_mpc.iloc[:min_len]

    # --- Metrics ---
    avg_q_base = df_base['max_queue'].mean()
    avg_q_mpc = df_mpc['max_queue'].mean()
    improvement = ((avg_q_base - avg_q_mpc) / avg_q_base) * 100

    print(f"Average Max Queue (Baseline): {avg_q_base:.2f}")
    print(f"Average Max Queue (MPC):      {avg_q_mpc:.2f}")
    print(f"Improvement:                  {improvement:.2f}%")

    # --- Plotting ---
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 10), sharex=True)

    # Plot 1: Congestion Comparison
    ax1.plot(df_base['time'], df_base['max_queue'], label='Baseline (Standard)', color='gray', linestyle='--', alpha=0.8)
    ax1.plot(df_mpc['time'], df_mpc['max_queue'], label='Deep Learning MPC', color='red', linewidth=2)
    ax1.set_ylabel('Max Queue Length (Vehicles)')
    ax1.set_title(f'Congestion Comparison (Improvement: {improvement:.1f}%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Plot 2: Difference (Green = Better, Red = Worse)
    diff = df_base['max_queue'] - df_mpc['max_queue']
    ax2.fill_between(df_base['time'], 0, diff, where=(diff >= 0), facecolor='green', alpha=0.3, label='MPC Improvement')
    ax2.fill_between(df_base['time'], 0, diff, where=(diff < 0), facecolor='red', alpha=0.3, label='MPC Worse')
    ax2.plot(df_base['time'], diff, color='black', linewidth=0.5)
    ax2.set_ylabel('Queue Reduction (Vehicles)')
    ax2.set_xlabel('Time (s)')
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    ax2.axhline(0, color='black', linewidth=0.8)

    output_file = "data/logs/comparison_plot.png"
    plt.tight_layout()
    plt.savefig(output_file)
    print(f"Comparison plot saved to {output_file}")
    plt.show()

if __name__ == "__main__":
    compare()