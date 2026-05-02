"""Simulation Manager configuration.

All settings are driven by environment variables with sensible defaults
so the same image runs identically in dev and Docker. See `.env.example`.

Backward-compat: exports a `config` object that mimics the old
`simulation_and_control_panel/backend/config.py` interface (DEBUG,
USE_GUI, STEP_DELAY, HOST, PORT) so the legacy app.py code keeps working.
"""
from __future__ import annotations
import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ('1', 'true', 'yes', 'on')


# Repository root. By default it's two levels up from this file:
#   services/simulation_manager/config.py  →  ../..  →  <repo root>
_DEFAULT_PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(os.getenv('PROJECT_ROOT', str(_DEFAULT_PROJECT_ROOT)))


@dataclass(frozen=True)
class Config:
    # Server
    HOST: str = os.getenv('HOST', '0.0.0.0')
    PORT: int = int(os.getenv('PORT', '5000'))
    DEBUG: bool = _env_bool('DEBUG', os.getenv('FLASK_ENV', 'development') == 'development')

    # SUMO
    # SUMO_MODE: 'local'  → Manager spawns sumo / sumo-gui itself (current default for non-Docker dev)
    #            'remote' → SUMO is already running on the host; Manager connects via TCP (Docker default)
    SUMO_MODE: str = os.getenv('SUMO_MODE', 'local').lower()
    SUMO_HOST: str = os.getenv('SUMO_HOST', 'localhost')
    SUMO_PORT: int = int(os.getenv('SUMO_PORT', '8813'))
    USE_GUI: bool = _env_bool('USE_GUI', True)

    # Simulation behavior
    STEP_LENGTH: float = float(os.getenv('STEP_LENGTH', '1.0'))
    STEP_DELAY: float = float(os.getenv('STEP_DELAY', '0.1'))
    AUTO_START_STEPPING: bool = _env_bool('AUTO_START_STEPPING', True)

    # Scenarios. Default points to the existing repo location for backwards compat.
    # In Docker, mount the host scenarios folder and set SCENARIOS_DIR=/app/scenarios.
    SCENARIOS_DIR: str = os.getenv(
        'SCENARIOS_DIR',
        str(PROJECT_ROOT / 'simulation_and_control_panel' / 'scenarios'),
    )
    DEFAULT_SCENARIO: str = os.getenv('DEFAULT_SCENARIO', 'grid3x3')

    # ── Model Routing (Phase 3+) ─────────────────────────────────────
    # When MODEL_<NAME>_URL is set, the named model is routed through HTTP
    # to the given URL instead of the in-process adapter. Empty string
    # means use the in-process adapter (Phase 2 fallback).
    # Examples (set via environment, do NOT hardcode here):
    #   MODEL_GNN_URL=http://gnn_service:8002
    #   MODEL_MPC_URL=http://mpc_service:8003
    MODEL_GNN_URL: str = os.getenv('MODEL_GNN_URL', '')
    MODEL_MPC_URL: str = os.getenv('MODEL_MPC_URL', '')
    MODEL_TIMEOUT_MS: int = int(os.getenv('MODEL_TIMEOUT_MS', '2000'))
    MODEL_RESET_TIMEOUT_MS: int = int(os.getenv('MODEL_RESET_TIMEOUT_MS', '30000'))

    @property
    def DEFAULT_CONFIG_FILE(self) -> str:
        explicit = os.getenv('DEFAULT_CONFIG_FILE')
        if explicit:
            return explicit
        return os.path.join(
            self.SCENARIOS_DIR,
            self.DEFAULT_SCENARIO,
            f'{self.DEFAULT_SCENARIO}.sumo.cfg',
        )


config = Config()
