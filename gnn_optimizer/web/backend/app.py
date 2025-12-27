from flask import Flask, jsonify, request
from flask_socketio import SocketIO
from flask_cors import CORS
from service import RemoteOptimizationService # Import ONLY the remote service
    
app = Flask(__name__)
app.config['SECRET_KEY'] = 'gnn_secret'
CORS(app) # Allow React to connect

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize our Remote Traffic Service     
optimization_service = RemoteOptimizationService(socketio)

@app.route('/')
def index():
    return "GNN Traffic Signal Optimizer Backend is Running 🚀"

@app.route('/api/start', methods=['POST'])
def start():
    return jsonify(optimization_service.start_simulation())

@app.route('/api/stop', methods=['POST'])
def stop():
    return jsonify(optimization_service.stop_simulation())

@socketio.on('connect')
def handle_connect():
    print('✅ Client connected to Dashboard')

@socketio.on('disconnect')
def handle_disconnect():
    print('❌ Client disconnected')

if __name__ == '__main__':
    print("🌍 Starting Web Server on port 5001...")
    # Port must be 5001 to avoid conflict with Simulation Manager on 5000
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)