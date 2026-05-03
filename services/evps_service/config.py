"""EVPS Service configuration."""
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
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '8004'))
    DEBUG: bool = _env_bool('DEBUG', False)

    # Models directory (mirrors host repo at /workspace via Docker volume mounts)
    EVPS_MODELS_DIR: str = os.getenv(
        'EVPS_MODELS_DIR',
        '/workspace/services/emergency_vehicle_preemption',
    )

    # Inference behavior
    SEQUENCE_LENGTH: int = int(os.getenv('SEQUENCE_LENGTH', '10'))
    ETA_SMOOTHING_ALPHA: float = float(os.getenv('ETA_SMOOTHING_ALPHA', '0.3'))
    MAX_INFERENCE_MS: int = int(os.getenv('MAX_INFERENCE_MS', '500'))

    @property
    def ETA_MODEL_PATH(self) -> str:
        return os.path.join(self.EVPS_MODELS_DIR, 'models', 'saved', 'eta_predictor.h5')

    @property
    def ETA_SCALER_PATH(self) -> str:
        return os.path.join(self.EVPS_MODELS_DIR, 'data', 'scalers', 'eta_scaler.pkl')

    @property
    def ETA_TARGET_SCALER_PATH(self) -> str:
        return os.path.join(self.EVPS_MODELS_DIR, 'data', 'scalers', 'eta_target_scaler.pkl')

    @property
    def SAFETY_MODEL_PATH(self) -> str:
        return os.path.join(self.EVPS_MODELS_DIR, 'models', 'saved', 'outcome_safety_classifier.pkl')


config = Config()
