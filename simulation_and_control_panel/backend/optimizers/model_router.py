import requests
import time

class ModelRouter:
    is_binary_action = True

    def __init__(self, model_url: str, net_file: str = None):
        self.model_url = model_url
        self.net_file = net_file
        self.last_uncertainty = None
        self.last_inference_ms = None
        self.model_name = 'unknown'
        self._connect()

    def _connect(self):
        try:
            r = requests.get(f'{self.model_url}/health', timeout=5)
            r.raise_for_status()
            info = requests.get(f'{self.model_url}/info', timeout=5).json()
            self.model_name = info.get('name', 'unknown')
            action_space = info.get('action_space', 'binary')
            self.is_binary_action = (action_space == 'binary')
            
            # Tell model service to initialize this specific map on load
            if self.net_file:
                init_resp = requests.post(f'{self.model_url}/init', json={'net_file': self.net_file}, timeout=10)
                init_resp.raise_for_status()
                
            print(f'Model connected: {self.model_name} | action={action_space} | map={self.net_file}')
        except Exception as e:
            raise ConnectionError(f'Model unreachable or failed to init at {self.model_url}: {e}')

    def reinitialize(self, net_file: str):
        """Called when simulation scenario changes at runtime. Rebuilds GNN graph for new map."""
        try:
            self.net_file = net_file
            resp = requests.post(f'{self.model_url}/init', json={'net_file': net_file}, timeout=10)
            resp.raise_for_status()
            print(f'GNN graph successfully rebuilt for new map: {net_file}')
        except Exception as e:
            print(f'WARNING: GNN reinitialize failed: {e}')
            self.model_name = 'ERROR - needs reload'

    def predict(self, snapshot: dict) -> dict:
        try:
            t0 = time.perf_counter()
            resp = requests.post(f'{self.model_url}/predict', json=snapshot, timeout=5)
            t1 = time.perf_counter()
            self.last_inference_ms = round((t1 - t0) * 1000, 2)
            result = resp.json()
            self.last_uncertainty = result.get('uncertainty')
            return result.get('actions', {})
        except Exception as e:
            print(f'Model prediction failed: {e}')
            return {}  # Safe fallback

    def reset(self):
        try:
            requests.post(f'{self.model_url}/reset', timeout=3)
        except:
            pass
