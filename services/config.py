import os
import sys

# Simple .env loader to avoid adding dependencies if not needed
# Or we can assume the environment is set up. 
# But let's try to load .env manually if python-dotenv is not guaranteed.

def load_env(env_path):
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip()

# Load .env from the same directory as this config file
current_dir = os.path.dirname(os.path.abspath(__file__))
load_env(os.path.join(current_dir, '.env'))

class Config:
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
    DASHBOARD_CORS_ORIGIN = os.getenv('DASHBOARD_CORS_ORIGIN', 'http://localhost:5173')
    BACKEND_PATH = os.getenv('BACKEND_PATH', 'gnn_optimizer/web/backend')

    MANAGER_API = os.getenv('MANAGER_API', 'http://localhost:5000/api')
    MANAGER_WS = os.getenv('MANAGER_WS', 'http://localhost:5000')
    GNN_SERVICE_URL = os.getenv('GNN_SERVICE_URL', 'http://localhost:5001')
