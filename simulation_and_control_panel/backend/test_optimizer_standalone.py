import sys
import os

# 1. Get the absolute path of the 'backend' folder
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from optimizers.gnn_adapter import GNNTrafficOptimizer

def test_gnn_loading():
    print("1. Testing Model Loading...")
    
    # 2. CALCULATE ABSOLUTE PATHS (Crucial Fix)
    # We navigate up from 'backend' to the root where both projects live
    # backend -> simulation_and_control_panel -> [Common Root]
    
    # Assuming folder structure:
    #   [Common Root]/
    #       ├── simulation_and_control_panel/
    #       │       └── backend/test_optimizer_standalone.py
    #       └── gnn_optimizer/
    
    # Go up 2 levels from backend to find the common root
    project_root = os.path.abspath(os.path.join(current_dir, ".."))
    common_root = os.path.abspath(os.path.join(project_root, ".."))
    
    # Construct absolute paths to the GNN files
    gnn_folder = os.path.join(common_root, "services", "gnn_optimizer")
    
    MODEL_PATH = os.path.join(gnn_folder, "experiments", "saved_models", "final_marl_model.pth")
    NET_PATH = os.path.join(gnn_folder, "simulation", "network.net.xml")

    print(f"   📍 Absolute Net Path: {NET_PATH}")

    if not os.path.exists(NET_PATH):
        print(f"❌ Error: Network file not found at calculated path!")
        return

    try:
        # Pass the ABSOLUTE path
        optimizer = GNNTrafficOptimizer(MODEL_PATH, NET_PATH)
        print("✅ Model loaded successfully!")
    except Exception as e:
        print(f"❌ Failed to load model: {e}")
        # Print full trace if needed
        import traceback
        traceback.print_exc()
        return

    print("\n2. Testing Prediction (Mock Data)...")
    try:
        # Mock the data structure
        mock_snapshot = {
            "lanes": {
                "lane_1": {"queue_length": 5, "occupancy": 0.5, "avg_speed": 10.0, "co2": 0.1, "waiting_time": 20},
            },
            "intersections": {
                "tls_1": {"phase_index": 0, "time_to_switch": 5}
            }
        }
        
        actions = optimizer.predict(mock_snapshot)
        print(f"✅ Prediction successful! Actions received: {actions}")
    except Exception as e:
        print(f"❌ Prediction failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_gnn_loading()