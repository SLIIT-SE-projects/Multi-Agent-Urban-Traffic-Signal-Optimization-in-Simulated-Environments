"""HTTP-based ModelRouter implementation.

Calls a remote model service over HTTP using the contract defined in
contracts/openapi/model_service.yaml. Handles timeouts, transient
failures, and falls back to last-known-good actions so the simulation
keeps running even if the model service is temporarily unreachable.

Used by the Simulation Manager from Phase 3 onward when the
MODEL_<NAME>_URL environment variable is set for a given model.
"""
from __future__ import annotations
import time
from typing import Optional

import requests

from routing.model_router import ModelRouter


class HttpModelRouter(ModelRouter):
    """ModelRouter that calls a remote model service over HTTP."""

    def __init__(
        self,
        model_name: str,
        base_url: str,
        timeout_ms: int = 2000,
        reset_timeout_ms: int = 30000,
        auth_token: Optional[str] = None,
    ):
        self._name = model_name
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_ms / 1000.0
        self._reset_timeout = reset_timeout_ms / 1000.0
        self._headers = {"Content-Type": "application/json"}
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"

        self._session_id: Optional[str] = None
        self._last_actions: dict = {}
        self._last_telemetry: dict = {}
        self._info_cache: Optional[dict] = None
        self._created_at = time.time()
        self._fallback_count = 0
        self._call_count = 0

    # ------------------------------------------------------------------
    # Contract methods
    # ------------------------------------------------------------------

    def info(self) -> dict:
        if self._info_cache is not None:
            return self._info_cache
        try:
            resp = requests.get(
                f"{self._base_url}/info",
                timeout=self._timeout,
                headers=self._headers,
            )
            resp.raise_for_status()
            self._info_cache = resp.json()
            return self._info_cache
        except Exception as exc:
            print(f"[HttpRouter:{self._name}] /info failed: {exc} — using defaults")
            # Conservative defaults so the Manager doesn't panic on /info failure
            return {
                "name": self._name,
                "version": "unknown",
                "snapshot_schema_version": "1",
                "action_schema_version": "1",
                "decision_interval_steps": 15,
                "action_types_supported": ["binary_switch", "set_phase"],
                "supports_warm_start": False,
                "max_inference_ms": int(self._timeout * 1000),
            }

    def health(self) -> dict:
        try:
            resp = requests.get(
                f"{self._base_url}/health",
                timeout=self._timeout,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return {
                "status": "unreachable",
                "model_loaded": False,
                "session_id": self._session_id,
                "error": str(exc),
                "uptime_seconds": time.time() - self._created_at,
            }

    def reset(self, *, session_id: str, network: dict, config: dict) -> dict:
        """Send /reset to the remote service.

        /reset can be slow (model weight loading, graph construction), so we
        use a longer timeout than /predict.
        """
        payload = {
            "session_id": session_id,
            "scenario": (config or {}).get("scenario") or (network or {}).get("scenario_name"),
            "network": network or {},
            "config": config or {},
        }
        try:
            resp = requests.post(
                f"{self._base_url}/reset",
                json=payload,
                timeout=self._reset_timeout,
                headers=self._headers,
            )
            resp.raise_for_status()
            self._session_id = session_id
            self._last_actions = {}
            self._fallback_count = 0
            self._call_count = 0
            self._info_cache = None  # Force refetch in case the model reports new metadata
            print(f"[HttpRouter:{self._name}] /reset OK session={session_id}")
            return resp.json()
        except requests.Timeout:
            raise RuntimeError(
                f"[HttpRouter:{self._name}] /reset timed out after {self._reset_timeout}s"
            )
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = resp.json().get("detail", "")
            except Exception:
                detail = resp.text if 'resp' in dir() else ''
            raise RuntimeError(
                f"[HttpRouter:{self._name}] /reset failed ({exc}): {detail}"
            )
        except Exception as exc:
            raise RuntimeError(f"[HttpRouter:{self._name}] /reset error: {exc}")

    def predict(self, *, session_id: str, step: int, snapshot: dict) -> dict:
        """Send /predict, returning the response or a fallback on failure."""
        self._call_count += 1
        payload = {
            "session_id": session_id,
            "step": step,
            "snapshot": snapshot,
        }
        try:
            resp = requests.post(
                f"{self._base_url}/predict",
                json=payload,
                timeout=self._timeout,
                headers=self._headers,
            )
            resp.raise_for_status()
            response = resp.json()

            # Cache for fallback
            self._last_actions = response.get("actions", {})
            self._last_telemetry = response.get("telemetry", {})
            return response
        except requests.Timeout:
            self._fallback_count += 1
            print(
                f"[HttpRouter:{self._name}] /predict TIMEOUT after "
                f"{self._timeout * 1000:.0f}ms — fallback #{self._fallback_count}"
            )
            return self._fallback_response(session_id, step, reason="timeout")
        except requests.HTTPError as exc:
            self._fallback_count += 1
            print(
                f"[HttpRouter:{self._name}] /predict HTTP error: {exc} "
                f"— fallback #{self._fallback_count}"
            )
            return self._fallback_response(session_id, step, reason=str(exc))
        except Exception as exc:
            self._fallback_count += 1
            print(
                f"[HttpRouter:{self._name}] /predict error: {exc} "
                f"— fallback #{self._fallback_count}"
            )
            return self._fallback_response(session_id, step, reason=str(exc))

    def teardown(self) -> None:
        """Best-effort: tell the remote service we're done."""
        try:
            requests.post(
                f"{self._base_url}/teardown",
                json={"session_id": self._session_id},
                timeout=2.0,
                headers=self._headers,
            )
        except Exception:
            pass
        self._session_id = None
        self._last_actions = {}
        self._last_telemetry = {}
        self._info_cache = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _fallback_response(self, session_id: str, step: int, reason: str) -> dict:
        """Build a fallback response when the remote service fails.

        Returns the last-known-good actions (which may be empty on the
        very first call). The Manager applies these actions as if the
        model had returned them — so on first-call failure, no actions
        are applied and the simulation runs with default SUMO control.
        """
        return {
            "session_id": session_id,
            "step": step,
            "actions": dict(self._last_actions),
            "telemetry": {
                "inference_time_ms": 0.0,
                "model_specific": {
                    "fallback": True,
                    "fallback_reason": reason,
                    "fallback_count": self._fallback_count,
                    "call_count": self._call_count,
                },
            },
        }

    @property
    def adapter(self):
        # HTTP routers have no in-process adapter to expose.
        return None
