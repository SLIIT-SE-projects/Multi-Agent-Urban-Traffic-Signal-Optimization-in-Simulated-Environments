import requests
import time
import sys

BASE_URL = "http://localhost:5000/api"

def run_mpc_simulation():
    print("🚀 Initializing Simulation with MPC Control...")
    
    # 1. Check Backend Health
    try:
        requests.get(f"{BASE_URL}/health")
    except requests.exceptions.ConnectionError:
        print("❌ Error: Backend is not running. Please run 'python simulation_and_control_panel/backend/app.py' first.")
        sys.exit(1)

    # 2. Start Simulation (if not running)
    print("1️⃣  Starting Simulation environment...")
    res = requests.post(f"{BASE_URL}/simulation/start")
    print(f"   Response: {res.json()}")

    # 3. Load MPC Optimizer
    print("2️⃣  Loading MPC Optimizer...")
    res = requests.post(f"{BASE_URL}/optimizer/load", json={"type": "mpc"})
    if res.status_code == 200:
        print("   ✅ MPC Optimizer Loaded Successfully")
    else:
        print(f"   ❌ Failed to load MPC: {res.text}")
        sys.exit(1)

    # 4. Start Auto-Stepping
    print("3️⃣  Starting Auto-Stepping...")
    res = requests.post(f"{BASE_URL}/simulation/auto-step/start")
    print(f"   Response: {res.json()}")

    print("\n✅ Simulation is running with MPC.")
    print("Check the Sumo GUI window to see the traffic.")
    print("Press Ctrl+C to stop the monitoring script (Simulation will continue running).")

    # Monitor loop
    try:
        while True:
            res = requests.get(f"{BASE_URL}/simulation/status")
            if res.status_code == 200:
                data = res.json()
                step = data.get("current_step", 0)
                # We can also get vehicle count
                v_res = requests.get(f"{BASE_URL}/simulation/vehicles")
                v_count = v_res.json().get("vehicle_count", 0) if v_res.status_code == 200 else "?"
                
                print(f"\r⏳ Step: {step} | Vehicles: {v_count} | Mode: MPC", end="")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopped monitoring.")

if __name__ == "__main__":
    run_mpc_simulation()
