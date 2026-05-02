"""In-process implementation of ModelRouter.

Phase 2 wraps the existing GNN/MPC adapters into the contract-shaped
interface without crossing a network boundary. Phase 3 will replace this
with an HTTP-based router for GNN; this in-process variant remains as a
fallback and as the preferred mode for development without containers.
"""
from __future__ import annotations
import time
from typing import Optional

from routing.model_router import ModelRouter


# Default metadata per known internal model. Phase 3+ moves these into
# each model service's own GET /info endpoint over HTTP.
_DEFAULTS = {
    'gnn': {
        'name': 'gnn',
        'version': '1.0.0',
        'snapshot_schema_version': '1',
        'action_schema_version': '1',
        'decision_interval_steps': 15,
        'action_types_supported': ['binary_switch'],
        'supports_warm_start': True,
        'max_inference_ms': 2000,
        'description': 'Recurrent HGAT MARL with MC Dropout uncertainty',
        'author': 'internal',
    },
    'mpc': {
        'name': 'mpc',
        'version': '1.0.0',
        'snapshot_schema_version': '1',
        'action_schema_version': '1',
        'decision_interval_steps': 15,
        'action_types_supported': ['set_phase'],
        'supports_warm_start': True,
        'max_inference_ms': 2000,
        'description': 'Model Predictive Control with LSTM demand predictor',
        'author': 'internal',
    },
}


class InProcessModelRouter(ModelRouter):
    """Wraps a local adapter into the standard ModelRouter contract."""

    def __init__(self, model_name: str, adapter):
        self._name = model_name
        self._adapter = adapter
        self._session_id: Optional[str] = None
        self._created_at = time.time()

    # ---------------------------------------------------------------------
    # Contract methods
    # ---------------------------------------------------------------------

    def info(self) -> dict:
        return dict(_DEFAULTS.get(self._name, {
            'name': self._name,
            'version': '1.0.0',
            'snapshot_schema_version': '1',
            'action_schema_version': '1',
            'decision_interval_steps': 15,
            'action_types_supported': ['binary_switch', 'set_phase'],
            'supports_warm_start': True,
            'max_inference_ms': 2000,
        }))

    def health(self) -> dict:
        return {
            'status': 'ok' if self._adapter is not None else 'not_ready',
            'model_loaded': self._adapter is not None,
            'session_id': self._session_id,
            'uptime_seconds': time.time() - self._created_at,
        }

    def reset(self, *, session_id: str, network: dict, config: dict) -> dict:
        self._session_id = session_id
        if hasattr(self._adapter, 'reset'):
            try:
                self._adapter.reset()
            except Exception as exc:
                print(f"[InProcessRouter] adapter.reset() failed: {exc}")
        return {'status': 'ready', 'session_id': session_id}

    def predict(self, *, session_id: str, step: int, snapshot: dict) -> dict:
        # Existing adapters take a flat snapshot of the form
        # {"intersections": {...}, "lanes": {...}}; the contract puts that
        # under a top-level 'snapshot' key. Accept either shape.
        adapter_input = snapshot.get('snapshot', snapshot)

        start = time.time()
        raw_actions = self._adapter.predict(adapter_input) or {}
        inference_ms = (time.time() - start) * 1000.0

        actions = self._translate_actions(raw_actions)
        telemetry = self._build_telemetry(inference_ms)

        return {
            'session_id': session_id,
            'step': step,
            'actions': actions,
            'telemetry': telemetry,
        }

    def teardown(self) -> None:
        self._adapter = None
        self._session_id = None

    @property
    def adapter(self):
        return self._adapter

    # ---------------------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------------------

    def _translate_actions(self, raw_actions: dict) -> dict:
        """Convert legacy adapter outputs into contract-shaped actions."""
        info = _DEFAULTS.get(self._name, {})
        types = info.get('action_types_supported', [])

        # GNN: returns {tls_id: 0|1}, marked with is_binary_action = True
        if 'binary_switch' in types and getattr(self._adapter, 'is_binary_action', False):
            return {
                tls_id: {'type': 'binary_switch', 'value': int(value)}
                for tls_id, value in raw_actions.items()
            }
        # MPC: returns {tls_id: phase_index}
        if 'set_phase' in types:
            return {
                tls_id: {'type': 'set_phase', 'value': int(value)}
                for tls_id, value in raw_actions.items()
            }
        # Unknown adapter — best-effort fallback to set_phase
        return {
            tls_id: {'type': 'set_phase', 'value': int(value)}
            for tls_id, value in raw_actions.items()
        }

    def _build_telemetry(self, inference_ms: float) -> dict:
        telemetry = {'inference_time_ms': round(inference_ms, 2)}
        if hasattr(self._adapter, 'get_telemetry'):
            try:
                tel = self._adapter.get_telemetry() or {}
            except Exception:
                tel = {}
            telemetry['per_node_latency_ms'] = tel.get('perNodeLatencyMs', {})
            telemetry['per_node_uncertainty'] = tel.get('perNodeUncertainty', {})
            telemetry['layer_activations'] = tel.get('layerActivations', {})
            telemetry['model_specific'] = {
                'uncertainty_score': tel.get('uncertaintyScore', 0),
            }
        return telemetry
