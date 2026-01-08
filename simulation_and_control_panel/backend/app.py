from flask import Flask, jsonify, request
from flask_sock import Sock
from flask_socketio import SocketIO
from flask_cors import CORS
from Controllers.simulation_controller import SimulationController
from Controllers.scenario_controller import ScenarioController
from Controllers.data_controller import DataController
from Controllers.state_controller import StateController
from Controllers.green_wave_controller import GreenWaveController
from config import config
from flask_socketio import SocketIO
import os
import json

app = Flask(__name__)
CORS(app)  # Allow frontend to connect
sock = Sock(app) # Initialize raw WebSocket support

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# CHANGE THIS to your actual config file!
# CONFIG_FILE = os.path.join(BASE_DIR, "..", "scenarios", "mapishara.sumo.cfg")
#CONFIG_FILE = os.path.join(BASE_DIR, "..", "scenarios", "grid3x3", "grid3x3.sumo.cfg")
CONFIG_FILE = os.path.join(BASE_DIR, "..", "..", "services", "emergency_vehicle_preemption", "simulation", "config", "katunayake.sumocfg")

# Initialize controllers
green_wave_controller = GreenWaveController(use_gui=config.USE_GUI)

sim_controller = SimulationController(
    CONFIG_FILE, 
    use_gui=config.USE_GUI,
    step_delay=config.STEP_DELAY,
    socketio_instance=socketio,
    green_wave_controller=green_wave_controller
)

data_controller = DataController(sim_controller)
scenario_controller = ScenarioController(sim_controller)
state_controller = StateController(sim_controller, data_controller)

# ============================================================================
# GREEN WAVE WEBSOCKET
# ============================================================================
@sock.route('/ws')
def green_wave_ws(ws):
    green_wave_controller.set_websocket(ws)
    try:
        while True:
            data = ws.receive()
            if data:
                try:
                    message = json.loads(data)
                    if message.get("type") == "switch_ev":
                        green_wave_controller.switch_vehicle(message.get("ev_id"))
                except:
                    pass
    except Exception as e:
        print(f"WS Error: {e}")
    finally:
        green_wave_controller.disconnect_websocket()


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "message": "API is running"})


# ============================================================================
# SIMULATION LIFECYCLE ENDPOINTS
# ============================================================================

@app.route('/api/simulation/start', methods=['POST'])
def start_simulation():
    result = sim_controller.start()
    return jsonify(result)


@app.route('/api/simulation/step', methods=['POST'])
def step_simulation():
    result = sim_controller.step()
    # If step succeeded, get current data
    if result.get("status") == "success":
        data = data_controller.get_current_data()
        result.update(data)
    return jsonify(result)


@app.route('/api/simulation/pause', methods=['POST'])
def pause_simulation():
    result = sim_controller.pause()
    return jsonify(result)


@app.route('/api/simulation/resume', methods=['POST'])
def resume_simulation():
    result = sim_controller.resume()
    return jsonify(result)


@app.route('/api/simulation/stop', methods=['POST'])
def stop_simulation():
    result = sim_controller.stop()
    return jsonify(result)


# ============================================================================
# AUTO-STEPPING ENDPOINTS
# ============================================================================

@app.route('/api/simulation/auto-step/start', methods=['POST'])
def start_auto_step():
    data = request.get_json(silent=True) or {}
    step_delay = data.get('step_delay', None)  # None will use config default
    result = sim_controller.start_auto_stepping(step_delay)
    return jsonify(result)


@app.route('/api/simulation/auto-step/pause', methods=['POST'])
def pause_auto_step():
    result = sim_controller.pause_auto_stepping()
    return jsonify(result)


@app.route('/api/simulation/auto-step/resume', methods=['POST'])
def resume_auto_step():
    result = sim_controller.resume_auto_stepping()
    return jsonify(result)


@app.route('/api/simulation/auto-step/stop', methods=['POST'])
def stop_auto_step():
    result = sim_controller.stop_auto_stepping()
    return jsonify(result)


# ============================================================================
# SCENARIO MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/scenarios', methods=['GET'])
def get_scenarios():
    """Get list of available scenarios"""
    result = scenario_controller.get_available_scenarios()
    return jsonify(result)


@app.route('/api/simulation/switch-scenario', methods=['POST'])
def switch_scenario():
    """Switch to a different scenario"""
    data = request.json
    scenario_name = data.get('scenario_name')
    
    if not scenario_name:
        return jsonify({"status": "error", "message": "scenario_name is required"}), 400
    
    result = scenario_controller.switch_scenario(scenario_name)
    return jsonify(result)


@app.route('/api/simulation/reload', methods=['POST'])
def reload_scenario():
    """Reload the current scenario from the beginning"""
    result = scenario_controller.reload_scenario()
    return jsonify(result)


@app.route('/api/simulation/current-scenario', methods=['GET'])
def get_current_scenario():
    """Get information about the currently loaded scenario"""
    result = scenario_controller.get_current_scenario_info()
    return jsonify(result)


# ============================================================================
# DATA RETRIEVAL ENDPOINTS
# ============================================================================

@app.route('/api/simulation/data', methods=['GET'])
def get_data():
    """Get current simulation data (vehicles, traffic lights)"""
    data = data_controller.get_current_data()
    return jsonify(data)


@app.route('/api/simulation/status', methods=['GET'])
def get_status():
    """Get simulation status"""
    status = data_controller.get_status()
    return jsonify(status)


@app.route('/api/simulation/vehicles', methods=['GET'])
def get_vehicles():
    """Get vehicle count and IDs"""
    result = data_controller.get_vehicle_count()
    return jsonify(result)


@app.route('/api/simulation/vehicles/<vehicle_id>', methods=['GET'])
def get_vehicle(vehicle_id):
    """Get detailed information about a specific vehicle"""
    result = data_controller.get_vehicle_details(vehicle_id)
    return jsonify(result)


@app.route('/api/simulation/traffic-lights', methods=['GET'])
def get_traffic_lights():
    """Get all traffic light states"""
    result = data_controller.get_traffic_light_states()
    return jsonify(result)


# ============================================================================
# STATE MANAGEMENT ENDPOINTS
# ============================================================================

@app.route('/api/simulation/save-state', methods=['POST'])
def save_state():
    """Save current simulation state"""
    data = request.json
    state_name = data.get('state_name', 'default')
    result = state_controller.save_state(state_name)
    return jsonify(result)


@app.route('/api/simulation/states', methods=['GET'])
def get_saved_states():
    """Get list of all saved states"""
    result = state_controller.get_saved_states()
    return jsonify(result)


@app.route('/api/simulation/states/<state_id>', methods=['GET'])
def get_state_details(state_id):
    """Get details about a specific saved state"""
    result = state_controller.get_state_details(state_id)
    return jsonify(result)


@app.route('/api/simulation/states/<state_id>', methods=['DELETE'])
def delete_state(state_id):
    """Delete a saved state"""
    result = state_controller.delete_state(state_id)
    return jsonify(result)


@app.route('/api/simulation/restore-state/<state_id>', methods=['POST'])
def restore_state(state_id):
    """Restore to a saved state"""
    result = state_controller.restore_state(state_id)
    return jsonify(result)


@app.route('/api/simulation/states', methods=['DELETE'])
def clear_all_states():
    """Delete all saved states"""
    result = state_controller.clear_all_states()
    return jsonify(result)

@app.route('/api/optimizer/load', methods=['POST'])
def load_optimizer():
    type = request.json.get('type', 'gnn')
    sim_controller.load_optimizer(type)
    return jsonify({"status": "success", "message": f"{type} optimizer loaded"})

@app.route('/api/optimizer/toggle', methods=['POST'])
def toggle_optimizer():
    # Enable/Disable logic in controller
    pass

@app.route('/api/optimizer/unload', methods=['POST'])
def unload_optimizer():
    result = sim_controller.unload_optimizer()
    return jsonify(result)



@app.route('/api/simulation/topology', methods=['GET'])
def get_topology():
    """Get the network topology (intersections, lanes, edges)"""
    result = sim_controller.get_network_topology()
    return jsonify(result)


# ============================================================================
# MPC BASELINE ENDPOINTS
# ============================================================================

BASELINE_FILE = os.path.join(BASE_DIR, "mpc_baseline_metrics.json")

@app.route('/api/mpc/baseline', methods=['GET'])
def get_mpc_baseline():
    """Get the saved baseline metrics if they exist"""
    if os.path.exists(BASELINE_FILE):
        try:
            with open(BASELINE_FILE, 'r') as f:
                data = json.load(f)
            return jsonify({"status": "success", "data": data})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)})
    else:
        return jsonify({"status": "not_found", "message": "No baseline file found"}), 404

@app.route('/api/mpc/baseline', methods=['POST'])
def save_mpc_baseline():
    """Save the current run metrics as the baseline"""
    data = request.json
    try:
        with open(BASELINE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return jsonify({"status": "success", "message": "Baseline saved"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})



if __name__ == '__main__':
    print("=" * 60)
    print("Starting Traffic Simulation API...")
    print("=" * 60)
    print(f"Config file: {CONFIG_FILE}")
    print(f"GUI Mode: {config.USE_GUI}")
    print(f"Step delay: {config.STEP_DELAY}s")
    print(f"API will be available at: http://localhost:{config.PORT}")
    print("=" * 60)
    socketio.run(app, debug=config.DEBUG, port=config.PORT, host=config.HOST)