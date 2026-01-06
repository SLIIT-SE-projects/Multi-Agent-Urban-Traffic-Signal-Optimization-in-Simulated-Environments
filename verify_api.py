import requests
import time

BASE_URL = "http://localhost:5000/api"

def check_status():
    try:
        resp = requests.get(f"{BASE_URL}/simulation/status")
        print(f"Status: {resp.status_code}, Body: {resp.json()}")
    except Exception as e:
        print(f"Status check failed: {e}")

def start_sim():
    try:
        resp = requests.post(f"{BASE_URL}/simulation/start")
        print(f"Start: {resp.status_code}, Body: {resp.json()}")
    except Exception as e:
        print(f"Start failed: {e}")

if __name__ == "__main__":
    check_status()
    start_sim()
    for i in range(10):
        check_status()
        time.sleep(1)
