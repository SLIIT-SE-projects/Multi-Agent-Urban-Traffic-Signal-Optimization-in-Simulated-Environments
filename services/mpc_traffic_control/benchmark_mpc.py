"""
benchmark_mpc.py
================
Standalone benchmark script for the MPC Traffic Signal Optimizer.
Mirrors the structure of benchmark_gnn.py used by the GNN team.

Runs two headless SUMO simulations:
  1. Baseline  — SUMO's built-in fixed-time signal control
  2. MPC       — MPC + LSTM demand prediction controlling the signals

Produces:
  • Terminal results table with % improvement per metric
  • 4 individual PNG plots  (queue, wait, speed, cost)
  • 1 combined summary PNG (4 subplots + improvement text)

Usage:
    cd services/mpc_traffic_control
    python benchmark_mpc.py
"""

import os
import sys
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')           # Headless — no display needed
import matplotlib.pyplot as plt

# ── Path Setup ────────────────────────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
MPC_SRC_PATH = os.path.join(SCRIPT_DIR, "src")

if MPC_SRC_PATH not in sys.path:
    sys.path.insert(0, MPC_SRC_PATH)

# SUMO must be on PATH (set SUMO_HOME env variable)
if "SUMO_HOME" in os.environ:
    tools = os.path.join(os.environ["SUMO_HOME"], "tools")
    if tools not in sys.path:
        sys.path.append(tools)

import traci

from traffic_mpc.core.controller  import MPCController
from traffic_mpc.core.prediction  import DemandPredictor
from traffic_mpc.config.settings  import MPCConfig, OptimizationConfig

# ── Configuration ─────────────────────────────────────────────────────────────
STEPS          = 1000           # Simulation steps (match GNN benchmark)
FLOW_RATE      = 300            # vehicles/hour — change to 100/200/300/400
ACTION_INTERVAL = 15            # MPC re-optimizes every N steps
LANE_CAPACITY  = 20.0           # For LSTM input normalisation

# Cost weights (mirror GNN's W_QUEUE / W_WAIT from TrainConfig)
W_QUEUE = 1.0
W_WAIT  = 0.5

# Paths
SCENARIO_DIR = os.path.join(PROJECT_ROOT,
    "simulation_and_control_panel", "scenarios", "grid3x3")
SUMO_CFG     = os.path.join(SCENARIO_DIR, "grid3x3.sumo.cfg")
NET_FILE     = os.path.join(SCENARIO_DIR, "grid3x3.net.xml")
DATA_DIR     = os.path.join(SCRIPT_DIR, "data")
MODEL_PATH   = os.path.join(DATA_DIR, "model.pth")
LANE_IDS_FILE = os.path.join(DATA_DIR, "lane_ids.json")
PLOT_DIR     = os.path.join(SCRIPT_DIR, "experiments", "plots")

# Plot style (matches GNN)
plt.style.use('bmh')


# ── Helpers ───────────────────────────────────────────────────────────────────

def _inject_flow(rate_veh_per_hour: float):
    """
    Injects vehicles dynamically via TraCI by scaling route departure rates.
    Mirrors simulation_controller.set_global_flow_rate().
    We use traci.route / traci.vehicle to add one vehicle per route
    proportionally to the desired rate, once per step.
    Instead of the full injection logic, we scale using --scale on the
    loaded demand (simpler for a standalone benchmark).
    """
    # Nothing to do here — we pass --scale via SUMO command directly.
    pass


def get_metrics():
    """
    Read per-step metrics from live TraCI connection.
    Returns: (total_queue, total_wait, avg_speed, throughput, cost)
    """
    lane_ids = traci.lane.getIDList()

    total_queue = 0
    total_wait  = 0
    total_speed = 0
    n_lanes     = 0

    for lid in lane_ids:
        if lid.startswith(":"):
            continue          # skip internal junctions
        total_queue += traci.lane.getLastStepHaltingNumber(lid)
        total_wait  += traci.lane.getWaitingTime(lid)
        total_speed += traci.lane.getLastStepMeanSpeed(lid)
        n_lanes += 1

    avg_speed   = total_speed / n_lanes if n_lanes > 0 else 0.0
    throughput  = traci.simulation.getArrivedNumber()
    cost        = W_QUEUE * total_queue + W_WAIT * total_wait

    return float(total_queue), float(total_wait), float(avg_speed), \
           float(throughput), float(cost)


def _build_sumo_cmd(flow_rate):
    """Build the SUMO headless command with flow rate scaling."""
    # vehicles/hour → scale factor relative to baseline demand.
    # Base scenario is calibrated at ~300 veh/hr.  We scale proportionally.
    BASE_FLOW = 300.0
    scale = max(0.01, flow_rate / BASE_FLOW)
    return [
        "sumo",
        "-c", SUMO_CFG,
        "--start",
        "--scale", str(scale),
        "--no-warnings",
        "--no-step-log",
    ]


# ── MPC Setup (called after traci.start) ─────────────────────────────────────

def _setup_mpc():
    """
    Initialise one MPCController per intersection and the global DemandPredictor.
    Mirrors MPCTrafficOptimizer._initialize_controllers() from mpc_adapter.py.
    """
    mpc_cfg = MPCConfig(
        prediction_horizon=20,
        control_horizon=5,
        min_green_time=5,
        max_green_time=60,
    )
    opt_cfg = OptimizationConfig()

    controllers  = {}   # tls_id -> {model, green_phases}
    cycle_plans  = {}   # tls_id -> {start_time, durations, phases} | None

    tls_ids = traci.trafficlight.getIDList()

    for tls_id in tls_ids:
        logics = traci.trafficlight.getAllProgramLogics(tls_id)
        if not logics:
            continue
        logic  = logics[0]
        phases = logic.phases
        links  = traci.trafficlight.getControlledLinks(tls_id)

        lane_ids         = []
        lane_phase_idx   = []
        seen_lanes       = set()

        for link_idx, conns in enumerate(links):
            if not conns:
                continue
            for (lid, _, _) in conns:
                if lid in seen_lanes:
                    continue
                green_phase = -1
                for p_idx, p in enumerate(phases):
                    if link_idx < len(p.state) and p.state[link_idx].lower() == 'g':
                        green_phase = p_idx
                        break
                if green_phase != -1:
                    lane_ids.append(lid)
                    lane_phase_idx.append(green_phase)
                    seen_lanes.add(lid)

        if not lane_ids:
            continue

        try:
            ctrl = MPCController(
                mpc_config=mpc_cfg,
                opt_config=opt_cfg,
                lane_ids=lane_ids,
                num_phases=len(phases),
                lane_phase_indices=lane_phase_idx,
            )
            controllers[tls_id] = {"model": ctrl, "phases": phases}
            cycle_plans[tls_id] = None
        except Exception as e:
            print(f"   ⚠ Could not init MPC for {tls_id}: {e}")

    # Load lane ordering saved by train_model.py (ensures LSTM input alignment)
    all_lanes_ordered = []
    if os.path.exists(LANE_IDS_FILE):
        with open(LANE_IDS_FILE) as f:
            all_lanes_ordered = json.load(f)
    else:
        all_sets = set()
        for d in controllers.values():
            all_sets.update(d["model"].lane_ids)
        all_lanes_ordered = sorted(all_sets)

    print(f"   ✅ MPC Initialized for {len(controllers)} intersections.")
    print(f"   🔮 Demand Predictor: {len(all_lanes_ordered)} lanes | Model: {MODEL_PATH}")

    predictor = DemandPredictor(mpc_cfg, all_lanes_ordered, MODEL_PATH)

    return controllers, cycle_plans, predictor, all_lanes_ordered, mpc_cfg


def _apply_mpc_step(controllers, cycle_plans, predictor, all_lanes_ordered, current_time):
    """
    One MPC decision cycle: update LSTM history, predict demand,
    optimize green times for each TLS, apply phase actions.
    Mirrors the predict() loop from mpc_adapter.py.
    """
    # 1. Update LSTM history with current normalised queue occupancies
    current_flows = {}
    for lid in all_lanes_ordered:
        try:
            current_flows[lid] = traci.lane.getLastStepHaltingNumber(lid) / LANE_CAPACITY
        except Exception:
            current_flows[lid] = 0.0

    if predictor:
        predictor.update_history(current_flows)
        predicted = predictor.predict()          # shape [n_lanes, Np]
        demand_map = {lid: predicted[i] for i, lid in enumerate(all_lanes_ordered)}
    else:
        demand_map = {}

    # 2. Per-intersection optimization
    for tls_id, data in controllers.items():
        model = data["model"]
        plan  = cycle_plans.get(tls_id)

        # --- Execute current plan if still active ---
        if plan:
            elapsed = current_time - plan["start_time"]
            if elapsed < sum(plan["durations"]):
                # Find which phase we should be in
                target_phase = _phase_from_plan(plan, elapsed)
                try:
                    green_indices = [
                        i for i, p in enumerate(data["phases"])
                        if 'g' in p.state.lower() and 'y' not in p.state.lower()
                    ]
                    sumo_target = green_indices[target_phase] \
                        if target_phase < len(green_indices) else green_indices[-1]
                    if sumo_target != traci.trafficlight.getPhase(tls_id):
                        traci.trafficlight.setPhase(tls_id, sumo_target)
                except Exception:
                    pass
                continue
            else:
                # Plan expired
                cycle_plans[tls_id] = None

        # --- Re-optimize ---
        queues = {}
        for lid in model.lane_ids:
            try:
                queues[lid] = traci.lane.getLastStepHaltingNumber(lid)
            except Exception:
                queues[lid] = 0

        local_demand = np.zeros((model.n_lanes, model.N))
        for i, lid in enumerate(model.lane_ids):
            if lid in demand_map:
                local_demand[i, :] = demand_map[lid][:model.N]
            else:
                local_demand[i, :] = 0.25

        sat_flows = {}
        for lid in model.lane_ids:
            ll = lid.lower()
            if any(t in ll for t in ["left", "_l_", "turn", "lt"]):
                sat_flows[lid] = 0.35
            elif any(t in ll for t in ["right", "_r_", "rt"]):
                sat_flows[lid] = 0.40
            else:
                sat_flows[lid] = 0.50

        try:
            green_times = model.optimize(
                queues, demand=local_demand, capacities={}, sat_flows=sat_flows)
        except Exception:
            avail = model.CycleTime - model.cfg.yellow_time * model.Phases
            green_times = [avail / model.Phases] * model.Phases

        cycle_plans[tls_id] = {
            "start_time": current_time,
            "durations":  list(green_times),
            "phases":     list(range(len(green_times))),
        }
        # Start phase 0 of the new plan
        try:
            green_indices = [
                i for i, p in enumerate(data["phases"])
                if 'g' in p.state.lower() and 'y' not in p.state.lower()
            ]
            if green_indices:
                traci.trafficlight.setPhase(tls_id, green_indices[0])
        except Exception:
            pass


def _phase_from_plan(plan, elapsed):
    cumulative = 0
    for i, dur in enumerate(plan["durations"]):
        cumulative += dur
        if elapsed < cumulative:
            return plan["phases"][i]
    return plan["phases"][-1]


# ── Simulation Runner ─────────────────────────────────────────────────────────

def run_simulation(mode: str):
    """
    Run a full simulation in 'baseline' or 'mpc' mode.
    Returns: (queues, waits, speeds, throughputs, costs) as numpy arrays.
    """
    label = "Baseline (Fixed-Time)" if mode == "baseline" else "MPC Controller"
    print(f"\n[{label}] Starting simulation ({STEPS} steps @ {FLOW_RATE} veh/hr)...")

    sumo_cmd = _build_sumo_cmd(FLOW_RATE)
    traci.start(sumo_cmd)
    traci.simulationStep()     # Warm up one step so TraCI IDs are available

    controllers   = None
    cycle_plans   = None
    predictor     = None
    lane_order    = None
    mpc_cfg       = None

    if mode == "mpc":
        try:
            controllers, cycle_plans, predictor, lane_order, mpc_cfg = _setup_mpc()
        except Exception as e:
            print(f"   ❌ MPC setup failed: {e}")
            traci.close()
            return np.array([]), np.array([]), np.array([]), np.array([]), np.array([])

    queues      = []
    waits       = []
    speeds      = []
    throughputs = []
    costs       = []

    for t in range(STEPS):
        # MPC control — re-optimize every ACTION_INTERVAL steps
        if mode == "mpc" and t % ACTION_INTERVAL == 0 and controllers:
            current_time = traci.simulation.getTime()
            _apply_mpc_step(controllers, cycle_plans, predictor,
                            lane_order, current_time)

        traci.simulationStep()

        q, w, s, th, c = get_metrics()
        queues.append(q)
        waits.append(w)
        speeds.append(s)
        throughputs.append(th)
        costs.append(c)

        if t % 200 == 0:
            print(f"   Step {t:4d}: Queue={q:6.1f} veh | Speed={s:.2f} m/s | Wait={w:.1f} s")

    traci.close()
    print(f"[{label}] Done.")
    return (np.array(queues), np.array(waits),
            np.array(speeds), np.array(throughputs), np.array(costs))


# ── Plotting ──────────────────────────────────────────────────────────────────

def _plot_metric(base_data, mpc_data, title, ylabel, filename, color, higher_is_better=False):
    """Save one metric comparison plot (mirrors GNN plot_single_metric)."""
    x = range(len(base_data))
    plt.figure(figsize=(10, 6))

    plt.plot(x, base_data, label='Baseline (Fixed-Time)',
             color='#7f8c8d', linestyle='--', linewidth=1.5)
    plt.plot(x, mpc_data,  label='MPC Controller',
             color=color, linewidth=2)
    plt.fill_between(x, mpc_data, alpha=0.12, color=color)

    plt.title(title, fontsize=14, fontweight='bold')
    plt.ylabel(ylabel, fontsize=12)
    plt.xlabel('Simulation Steps', fontsize=12)
    plt.legend(loc='lower right' if higher_is_better else 'upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    path = os.path.join(PLOT_DIR, filename)
    plt.savefig(path, dpi=300)
    plt.close()
    print(f"   Saved: {path}")


def save_all_plots(base_data, mpc_data):
    os.makedirs(PLOT_DIR, exist_ok=True)

    base_q, base_w, base_s, base_th, base_c = base_data
    mpc_q,  mpc_w,  mpc_s,  mpc_th,  mpc_c  = mpc_data
    x = range(len(base_q))

    print("\n[Plotting] Generating graphs...")

    # ── 4 individual plots ────────────────────────────────────────────────────
    _plot_metric(base_q, mpc_q,
                 "Network Congestion — Queue Length",
                 "Vehicles (halted)", "benchmark_mpc_queue.png",
                 "#27ae60", higher_is_better=False)

    _plot_metric(base_w, mpc_w,
                 "Total Waiting Time",
                 "Accumulated Seconds", "benchmark_mpc_wait.png",
                 "#2980b9", higher_is_better=False)

    _plot_metric(base_s, mpc_s,
                 "Average Network Speed  (proxy for travel time)",
                 "Speed (m/s)", "benchmark_mpc_speed.png",
                 "#e67e22", higher_is_better=True)

    _plot_metric(base_c, mpc_c,
                 "Weighted Performance Cost  [W_queue·Q + W_wait·W]",
                 "Cost", "benchmark_mpc_cost.png",
                 "#8e44ad", higher_is_better=False)

    # ── Combined 4-subplot summary (mirrors GNN benchmark_summary.png) ────────
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(12, 18), sharex=True)

    def _subplot(ax, bd, md, title, ylabel, color, hib):
        ax.plot(x, bd, label='Baseline', color='#7f8c8d',
                linestyle='--', linewidth=1.5)
        ax.plot(x, md, label='MPC', color=color, linewidth=2)
        ax.fill_between(x, md, alpha=0.10, color=color)
        ax.set_title(title, fontweight='bold')
        ax.set_ylabel(ylabel)
        ax.legend(loc='lower right' if hib else 'upper left')
        ax.grid(True, alpha=0.3)

    _subplot(ax1, base_q, mpc_q, "Metric 1: Network Congestion (Queue Length)",
             "Vehicles", "#27ae60", False)
    _subplot(ax2, base_w, mpc_w, "Metric 2: Total Waiting Time",
             "Seconds", "#2980b9", False)
    _subplot(ax3, base_s, mpc_s, "Metric 3: Avg Speed (Higher = Less Travel Time)",
             "Speed (m/s)", "#e67e22", True)
    _subplot(ax4, base_c, mpc_c, "Metric 4: Weighted Performance Cost",
             "Cost", "#8e44ad", False)

    ax4.set_xlabel("Simulation Steps", fontsize=12)

    # Improvement % summary text at the bottom
    imp_wait  = (np.mean(base_w) - np.mean(mpc_w))  / max(np.mean(base_w), 1e-6) * 100
    imp_queue = (np.mean(base_q) - np.mean(mpc_q))  / max(np.mean(base_q), 1e-6) * 100
    imp_speed = (np.mean(mpc_s)  - np.mean(base_s)) / max(np.mean(base_s), 1e-6) * 100
    imp_cost  = (np.mean(base_c) - np.mean(mpc_c))  / max(np.mean(base_c), 1e-6) * 100

    summary = (
        f"MPC vs Baseline  |  Flow Rate: {FLOW_RATE} veh/hr  |  Steps: {STEPS}\n"
        f"Wait: {imp_wait:+.1f}%   Queue: {imp_queue:+.1f}%   "
        f"Speed: {imp_speed:+.1f}%   Cost: {imp_cost:+.1f}%"
    )
    plt.figtext(0.5, 0.015, summary,
                ha="center", fontsize=13,
                bbox={"facecolor": "white", "alpha": 0.85, "pad": 6})

    plt.tight_layout(rect=[0, 0.06, 1, 1])
    summary_path = os.path.join(PLOT_DIR, "benchmark_mpc_summary.png")
    plt.savefig(summary_path, dpi=300)
    plt.close()
    print(f"   Saved: {summary_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 55)
    print("   MPC TRAFFIC SIGNAL OPTIMIZATION — BENCHMARK")
    print(f"   Scenario: grid3x3  |  Flow: {FLOW_RATE} veh/hr  |  Steps: {STEPS}")
    print("=" * 55)

    # 1. Run both simulations
    base_data = run_simulation(mode="baseline")
    mpc_data  = run_simulation(mode="mpc")

    if len(mpc_data[0]) == 0:
        print("\n❌ MPC simulation failed. Exiting.")
        return

    base_q, base_w, base_s, base_th, base_c = base_data
    mpc_q,  mpc_w,  mpc_s,  mpc_th,  mpc_c  = mpc_data

    # 2. Calculate averages
    avg = lambda arr: float(np.mean(arr))

    # 3. Compute improvement %  (positive = MPC better)
    def pct_reduce(b, m):   # lower-is-better metrics
        return (avg(b) - avg(m)) / max(avg(b), 1e-6) * 100
    def pct_increase(b, m): # higher-is-better metrics
        return (avg(m) - avg(b)) / max(avg(b), 1e-6) * 100

    imp_wait  = pct_reduce(base_w, mpc_w)
    imp_queue = pct_reduce(base_q, mpc_q)
    imp_cost  = pct_reduce(base_c, mpc_c)
    imp_speed = pct_increase(base_s, mpc_s)
    imp_thru  = pct_increase(base_th, mpc_th)

    # 4. Print results table (matches GNN format)
    W = 26
    print(f"\n{'─'*70}")
    print("RESULTS SUMMARY")
    print(f"{'─'*70}")
    print(f"{'Metric':<{W}} | {'Baseline':>10} | {'MPC':>10} | {'Improvement':>12}")
    print("─" * 70)
    print(f"{'Avg Waiting Time (s)':<{W}} | {avg(base_w):>10.2f} | {avg(mpc_w):>10.2f} | {imp_wait:>+11.2f}%")
    print(f"{'Avg Queue Length (veh)':<{W}} | {avg(base_q):>10.2f} | {avg(mpc_q):>10.2f} | {imp_queue:>+11.2f}%")
    print(f"{'Avg Speed (m/s)':<{W}} | {avg(base_s):>10.2f} | {avg(mpc_s):>10.2f} | {imp_speed:>+11.2f}%")
    print(f"{'Total Throughput (veh)':<{W}} | {avg(base_th):>10.2f} | {avg(mpc_th):>10.2f} | {imp_thru:>+11.2f}%")
    print(f"{'Weighted Cost':<{W}} | {avg(base_c):>10.2f} | {avg(mpc_c):>10.2f} | {imp_cost:>+11.2f}%")
    print("─" * 70)
    print(f"\n  ✅ Overall Cost Reduction : {imp_cost:+.2f}%")
    print(f"  🚀 Speed Improvement      : {imp_speed:+.2f}%")
    print(f"  ⏱  Wait Time Reduction    : {imp_wait:+.2f}%")

    # 5. Save plots
    save_all_plots(base_data, mpc_data)

    print(f"\n  📊 Plots saved to: {PLOT_DIR}")
    print("=" * 55)


if __name__ == "__main__":
    main()
