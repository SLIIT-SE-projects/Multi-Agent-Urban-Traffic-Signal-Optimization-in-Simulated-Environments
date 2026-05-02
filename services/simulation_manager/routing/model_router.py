"""Model Router abstract interface.

Every model — internal (GNN, MPC) or external researcher — interacts with
the SimulationController through this interface. Phase 2 ships an
InProcessModelRouter that wraps adapters without crossing a network
boundary. Phase 3+ adds HttpModelRouter that calls a remote model service
over HTTP.

The interface mirrors the contract in:
  contracts/openapi/model_service.yaml
  contracts/schemas/snapshot.schema.json
  contracts/schemas/action.schema.json
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class ModelRouter(ABC):
    """Abstract interface every model implementation conforms to.

    A ModelRouter is created when the operator loads a model (via
    POST /api/optimizer/load) and discarded when unloaded. Per-step
    inference runs through `predict()`.
    """

    @abstractmethod
    def info(self) -> dict:
        """Return /info-equivalent metadata.

        Conforms to contracts/schemas/model_info.schema.json.
        """

    @abstractmethod
    def health(self) -> dict:
        """Return /health-equivalent status."""

    @abstractmethod
    def reset(self, *, session_id: str, network: dict, config: dict) -> dict:
        """Initialize the model for a new session.

        Called once when the simulation starts (or when a scenario
        switches). The full network topology is provided so the model
        can build any internal data structures.
        """

    @abstractmethod
    def predict(self, *, session_id: str, step: int, snapshot: dict) -> dict:
        """Compute actions for a snapshot.

        Returns a dict matching contracts/schemas/action.schema.json:
            {
              "session_id": str,
              "step": int,
              "actions": {tls_id: {type, ...}},
              "telemetry": {...}
            }
        """

    def teardown(self) -> None:
        """Release any held resources. Default is a no-op."""
        return

    @property
    def adapter(self) -> Optional[object]:
        """Underlying adapter, when one exists in-process.

        Used by legacy endpoints that need direct access to the adapter
        (for example /api/optimizer/mpc/internals). HTTP-only routers
        return None.
        """
        return None
