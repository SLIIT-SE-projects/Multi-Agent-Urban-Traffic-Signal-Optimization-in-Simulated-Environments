import requests
import time

BASE_URL = "http://localhost:5000/api"

def step_and_check():
    # 1. Step the simulation
    try:
        resp = requests.post(f"{BASE_URL}/simulation/step")
        print(f"Step Response: {resp.status_code}, {resp.json()}")
    except Exception as e:
        print(f"Step failed: {e}")
        return

    # 2. Check vehicles
    try:
        resp = requests.get(f"{BASE_URL}/simulation/data")
        data = resp.json()
        print(f"Step: {data.get('step')}, Vehicles: {data.get('vehicle_count')}")
        if data.get('vehicles'):
            print(f"Sample Vehicle: {data['vehicles'][0]}")
    except Exception as e:
        print(f"Data check failed: {e}")

if __name__ == "__main__":
    # Ensure it's running
    requests.post(f"{BASE_URL}/simulation/start")
    
    print("Stepping 10 times...")
    for i in range(10):
        step_and_check()
        time.sleep(0.5)
