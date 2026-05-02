"""GNN Service configuration.

All settings are environment-driven for parity with how the Simulation
Manager and other services are configured.
"""
from __future__ import annotations
import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


@dataclass(frozen=True)
class Config:
    # Server
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '8002'))
    DEBUG: bool = _env_bool('DEBUG', False)

    # Model weights — defaults assume the Docker /workspace volume mount
    MODEL_WEIGHTS_PATH: str = os.getenv(
        'MODEL_WEIGHTS_PATH',
        '/workspace/model_weights/final_marl_model_best.pth',
    )

    # Inference behavior
    MAX_INFERENCE_MS: int = int(os.getenv('MAX_INFERENCE_MS', '2000'))
    DECISION_INTERVAL_STEPS: int = int(os.getenv('DECISION_INTERVAL_STEPS', '15'))
    MC_DROPOUT_SAMPLES: int = int(os.getenv('MC_DROPOUT_SAMPLES', '20'))

    # Where to find scenarios when /reset doesn't pass an explicit net.xml path.
    # Defaults match the Manager's mount layout.
    SCENARIOS_DIR: str = os.getenv(
        'SCENARIOS_DIR',
        '/workspace/simulation_and_control_panel/scenarios',
    )


config = Config()
