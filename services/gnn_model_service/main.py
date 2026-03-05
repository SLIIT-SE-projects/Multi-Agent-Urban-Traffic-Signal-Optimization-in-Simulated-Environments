from fastapi import FastAPI
from pydantic import BaseModel
from predictor import GNNPredictor

app = FastAPI(title='GNN Traffic Signal Optimizer')
predictor = GNNPredictor()

class Snapshot(BaseModel):
    step: int = 0
    intersections: dict
    lanes: dict

class InitRequest(BaseModel):
    net_file: str

@app.post('/init')
def init_model(payload: InitRequest):
    try:
        predictor.initialize_graph(payload.net_file)
        return {'status': 'success', 'message': f'Graph initialized with {payload.net_file}'}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))

@app.get('/health')
def health():
    return {'status': 'ready'}

@app.get('/info')
def info():
    return {
        'name': 'GNN-PPO',
        'version': '1.0',
        'action_space': 'binary',
        'description': '2-hop HGAT + PPO, 79.7% cost reduction',
    }

@app.post('/predict')
def predict(snapshot: Snapshot):
    actions, uncertainty = predictor.predict(snapshot.dict())
    return {
        'actions': actions,
        'uncertainty': uncertainty,
        'metadata': {'model': 'GNN-PPO', 'step': snapshot.step}
    }

@app.post('/reset')
def reset():
    predictor.reset()
    return {'status': 'reset'}
