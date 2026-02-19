import os
import sys
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats
import traci

# Import backend controller
from runtime.green_wave_backend import controller

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SUMO_CONFIG = os.path.join(BASE_DIR, "simulation/config/colombo_mega_scenario.sumocfg")
RESULTS_DIR = os.path.join(BASE_DIR, "data/evaluation_results")
GRAPHS_DIR = os.path.join(BASE_DIR, "data/evaluation_results/graphs")

os.makedirs(RESULTS_DIR, exist_ok=True)
os.makedirs(GRAPHS_DIR, exist_ok=True)

NUM_RUNS_PER_SCENARIO = 10
CONGESTION_LEVELS = {
    "Low": "0.5",
    "Medium": "1.0",
    "High": "1.5"
}

# Save the original AI logic so we can restore it after the "Blind" runs
ORIGINAL_EVALUATE_SAFETY = controller._evaluate_safety

def reset_controller_memory():
    """Wipes the backend controller's memory between runs to prevent Ghost Data."""
    controller.fleet.clear()
    controller.active_override_tls_ids.clear()
    controller.smoothed_eta = None
    controller.ev_id = "EV_0"

def parse_tripinfo(xml_file):
    """Parses SUMO's tripinfo.xml to extract exact time metrics."""
    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        
        ev_travel_times = []
        civilian_time_losses = []
        
        for trip in root.findall('tripinfo'):
            veh_id = trip.get('id')
            duration = float(trip.get('duration'))
            time_loss = float(trip.get('timeLoss'))
            
            if veh_id.startswith("EV_"):
                ev_travel_times.append(duration)
            else:
                civilian_time_losses.append(time_loss)
                
        return {
            "avg_ev_travel_time": np.mean(ev_travel_times) if ev_travel_times else 0,
            "avg_civilian_delay": np.mean(civilian_time_losses) if civilian_time_losses else 0
        }
    except Exception as e:
        print(f"Error parsing XML {xml_file}: {e}")
        return {"avg_ev_travel_time": 0, "avg_civilian_delay": 0}

def run_simulation(mode, congestion_name, scale_factor, run_id):
    """Runs SUMO with fixed seeds and tracks safety metrics."""
    tripinfo_file = os.path.join(RESULTS_DIR, f"tripinfo_{mode}_{congestion_name}_{run_id}.xml")
    
    sumo_cmd = [
        "sumo", 
        "-c", SUMO_CONFIG, 
        "--scale", scale_factor, 
        "--tripinfo-output", tripinfo_file,
        "--seed", str(run_id) # Fixed seed for paired testing
    ]
    
    reset_controller_memory()
    
    # --- ABLATION LOGIC ---
    if mode == "blind":
        # Force the gatekeeper to always approve (Bypass AI Safety)
        controller._evaluate_safety = lambda tls_id, ev_id: True
    else:
        # Restore the real AI Gatekeeper for EVPS mode
        controller._evaluate_safety = ORIGINAL_EVALUATE_SAFETY
    
    traci.start(sumo_cmd)
    controller.running = True
    
    print(f"Running: Mode={mode.upper():<10} | Congestion={congestion_name:<6} | Seed={run_id}")
    
    # --- METRIC TRACKERS ---
    total_collisions = 0
    total_teleports = 0
    gatekeeper_interventions = 0
    previously_blocked_evs = set() # To count unique intervention events
    
    while traci.simulation.getMinExpectedNumber() > 0:
        if mode in ["evps", "blind"]:
            controller.simulation_step()
            
            # Track Gatekeeper Interventions (Only applies to Intelligent EVPS)
            if mode == "evps":
                for ev_id, ev_data in controller.fleet.items():
                    is_blocked = ev_data.get("safety_blocked", False)
                    # Detect the moment the flag flips from False to True
                    if is_blocked and ev_id not in previously_blocked_evs:
                        gatekeeper_interventions += 1
                        previously_blocked_evs.add(ev_id)
                    elif not is_blocked and ev_id in previously_blocked_evs:
                        previously_blocked_evs.remove(ev_id)
        else:
            traci.simulationStep() # Baseline

        # Track Physical Simulation Failures
        total_collisions += traci.simulation.getCollidingVehiclesNumber()
        total_teleports += traci.simulation.getStartingTeleportNumber()
            
    traci.close()
    controller.running = False
    
    metrics = parse_tripinfo(tripinfo_file)
    
    # Map mode to pretty names for the graphs
    mode_label = "Baseline"
    if mode == "blind": mode_label = "Blind Preemption"
    elif mode == "evps": mode_label = "Intelligent EVPS"

    return {
        "Mode": mode_label,
        "Congestion": congestion_name,
        "Run_ID": run_id,
        "EV_Travel_Time_sec": metrics["avg_ev_travel_time"],
        "Civilian_Delay_sec": metrics["avg_civilian_delay"],
        "Collisions": total_collisions,
        "Teleports_Gridlocks": total_teleports,
        "Gatekeeper_Interventions": gatekeeper_interventions
    }

def generate_graphs(df):
    """Generates all publication-ready charts including safety ablation visuals."""
    sns.set_theme(style="whitegrid", palette="muted")
    
    # Define standard color palette so modes remain consistent across graphs
    mode_colors = {"Baseline": "#808080", "Blind Preemption": "#d62728", "Intelligent EVPS": "#2ca02c"}
    
    # 1. EV Travel Time (The Efficiency Metric)
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="Congestion", y="EV_Travel_Time_sec", hue="Mode", palette=mode_colors, capsize=.1)
    plt.title("Emergency Vehicle Travel Time (Efficiency)", fontsize=14)
    plt.ylabel("Travel Time (Seconds)", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "1_efficiency_travel_time.png"), dpi=300)
    plt.close()

    # 2. Total Collisions (The Primary Safety Metric)
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="Congestion", y="Collisions", hue="Mode", palette=mode_colors, capsize=.1)
    plt.title("Physical Collisions Caused (Ablation Study)", fontsize=14)
    plt.ylabel("Number of Collisions (T-Bones)", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "2_safety_collisions.png"), dpi=300)
    plt.close()

    # 3. Teleports (The Gridlock/Deadlock Metric)
    plt.figure(figsize=(10, 6))
    sns.barplot(data=df, x="Congestion", y="Teleports_Gridlocks", hue="Mode", palette=mode_colors, capsize=.1)
    plt.title("Systemic Deadlocks (SUMO Teleports)", fontsize=14)
    plt.ylabel("Number of Teleports", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "3_safety_teleports.png"), dpi=300)
    plt.close()

    # 4. Gatekeeper Interventions (Proof of AI Activity)
    # Filter only Intelligent EVPS data
    evps_df = df[df["Mode"] == "Intelligent EVPS"]
    plt.figure(figsize=(8, 5))
    sns.barplot(data=evps_df, x="Congestion", y="Gatekeeper_Interventions", color="#2ca02c", capsize=.1)
    plt.title("AI Gatekeeper Interventions (Preemptions Denied)", fontsize=14)
    plt.ylabel("Number of Interventions", fontsize=12)
    plt.tight_layout()
    plt.savefig(os.path.join(GRAPHS_DIR, "4_gatekeeper_activity.png"), dpi=300)
    plt.close()
    
    print(f"\nSUCCESS: Generated 4 publication-ready graphs in {GRAPHS_DIR}")

def run_statistical_analysis(df):
    """Performs Paired T-Tests on Efficiency and Safety metrics."""
    print("\n" + "="*60)
    print("--- ABLATION STUDY & PAIRED STATISTICAL ANALYSIS ---")
    print("="*60)
    
    for congestion in CONGESTION_LEVELS.keys():
        print(f"\n>>> {congestion.upper()} CONGESTION SCENARIOS <<<")
        
        base_df = df[(df["Mode"] == "Baseline") & (df["Congestion"] == congestion)].sort_values("Run_ID")
        blind_df = df[(df["Mode"] == "Blind Preemption") & (df["Congestion"] == congestion)].sort_values("Run_ID")
        evps_df = df[(df["Mode"] == "Intelligent EVPS") & (df["Congestion"] == congestion)].sort_values("Run_ID")
        
        base_times = base_df["EV_Travel_Time_sec"].values
        blind_times = blind_df["EV_Travel_Time_sec"].values
        evps_times = evps_df["EV_Travel_Time_sec"].values
        
        blind_collisions = blind_df["Collisions"].values
        evps_collisions = evps_df["Collisions"].values

        # 1. TRAVEL TIME ANALYSIS (Baseline vs Intelligent EVPS)
        improvement = ((base_times.mean() - evps_times.mean()) / base_times.mean()) * 100
        t_stat_time, p_val_time = stats.ttest_rel(base_times, evps_times)
        
        print(f"\n  [Efficiency: Baseline vs Intelligent EVPS]")
        print(f"    Baseline Time: {base_times.mean():.2f}s | Intelligent Time: {evps_times.mean():.2f}s")
        print(f"    Improvement:   {improvement:.2f}% Faster")
        print(f"    P-Value:       {p_val_time:.5e} -> " + ("✅ Sig" if p_val_time < 0.05 else "❌ Not Sig"))

        # 2. SAFETY ABLATION ANALYSIS (Blind vs Intelligent EVPS)
        col_reduction = blind_collisions.mean() - evps_collisions.mean()
        # Handle zero variance case (if both are 0, t-test throws a warning)
        if blind_collisions.var() == 0 and evps_collisions.var() == 0:
            p_val_safe = 1.0
        else:
            t_stat_safe, p_val_safe = stats.ttest_rel(blind_collisions, evps_collisions)
        
        print(f"\n  [Safety: Blind Preemption vs Intelligent EVPS]")
        print(f"    Blind Collisions: {blind_collisions.mean():.1f} | Intelligent Collisions: {evps_collisions.mean():.1f}")
        print(f"    AI Prevention:    Prevented {col_reduction:.1f} collisions per run")
        print(f"    P-Value:          {p_val_safe:.5e} -> " + ("✅ Sig" if p_val_safe < 0.05 else "❌ Not Sig"))
        
        # 3. AI GATEKEEPER ACTIVITY
        print(f"\n  [AI Activity]")
        print(f"    Gatekeeper Interventions: {evps_df['Gatekeeper_Interventions'].mean():.1f} denials per run")

def main():
    print("Starting Automated EVPS Ablation Study (3 Modes, Paired Execution)...")
    all_results = []
    
    for congestion_name, scale in CONGESTION_LEVELS.items():
        for run_id in range(1, NUM_RUNS_PER_SCENARIO + 1):
            
            # 1. Baseline
            all_results.append(run_simulation("baseline", congestion_name, scale, run_id))
            
            # 2. Blind Preemption (Ablated AI)
            all_results.append(run_simulation("blind", congestion_name, scale, run_id))
            
            # 3. Intelligent EVPS (Full System)
            all_results.append(run_simulation("evps", congestion_name, scale, run_id))
            
    df = pd.DataFrame(all_results)
    csv_path = os.path.join(RESULTS_DIR, "ablation_evaluation_metrics.csv")
    df.to_csv(csv_path, index=False)
    print(f"\nSaved raw numerical data to: {csv_path}")
    
    generate_graphs(df)
    run_statistical_analysis(df)
    print("\nEvaluation Complete! Thesis graphs and statistical proofs generated.")

if __name__ == "__main__":
    main()