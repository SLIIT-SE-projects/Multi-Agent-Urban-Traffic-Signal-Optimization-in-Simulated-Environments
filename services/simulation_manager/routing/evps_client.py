"""HTTP client for the EVPS service.

Used by the Simulation Manager when EVPS_URL is set. Falls back to the
in-process EVPSAdapter otherwise (Phase 2 behavior preserved).

Provides the same surface area the Manager and app.py used to call on
the in-process adapter: toggle, spawn-notify, set-focus, set-priority,
plus per-step `step()` for the TraCI loop and broadcast relay.
"""
from __future__ import annotations
import time
from typing import Optional

import requests


class EvpsClient:
    """HTTP wrapper around the EVPS service."""

    def __init__(
        self,
        base_url: str,
        timeout_ms: int = 2000,
        auth_token: Optional[str] = None,
    ):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_ms / 1000.0
        self._headers = {"Content-Type": "application/json"}
        if auth_token:
            self._headers["Authorization"] = f"Bearer {auth_token}"

        self._session_id: Optional[str] = None
        self._fallback_count = 0
        self._created_at = time.time()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self, session_id: str) -> None:
        try:
            r = requests.post(
                f"{self._base_url}/reset",
                json={"session_id": session_id},
                timeout=self._timeout,
                headers=self._headers,
            )
            r.raise_for_status()
            self._session_id = session_id
        except Exception as exc:
            raise RuntimeError(f"[EvpsClient] /reset failed: {exc}")

    def toggle(self, enable: bool) -> dict:
        try:
            r = requests.post(
                f"{self._base_url}/toggle",
                json={"enable": enable},
                timeout=self._timeout,
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def teardown(self) -> None:
        try:
            requests.post(
                f"{self._base_url}/teardown",
                timeout=self._timeout,
                headers=self._headers,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Per-step
    # ------------------------------------------------------------------

    def step(self, snapshot: dict) -> dict:
        """Send /step with the enriched snapshot. Returns overrides + broadcasts.

        On failure, returns an empty result so the simulation keeps running.
        """
        try:
            r = requests.post(
                f"{self._base_url}/step",
                json=snapshot,
                timeout=self._timeout,
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            self._fallback_count += 1
            if self._fallback_count <= 3 or self._fallback_count % 100 == 0:
                print(f"[EvpsClient] /step error #{self._fallback_count}: {exc}")
            return {"overrides": {}, "broadcasts": {}, "released_locks": []}

    # ------------------------------------------------------------------
    # Fleet management
    # ------------------------------------------------------------------

    def register_ev(
        self,
        ev_id: str,
        priority: int = 1,
        vehicle_type: str = "ambulance",
    ) -> dict:
        try:
            r = requests.post(
                f"{self._base_url}/register_ev",
                json={
                    "ev_id": ev_id,
                    "priority": priority,
                    "vehicle_type": vehicle_type,
                },
                timeout=self._timeout,
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def set_focus(self, ev_id: str) -> dict:
        try:
            r = requests.post(
                f"{self._base_url}/set_focus",
                json={"ev_id": ev_id},
                timeout=self._timeout,
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def set_priority(self, ev_id: str, priority: int) -> dict:
        try:
            r = requests.post(
                f"{self._base_url}/set_priority",
                json={"ev_id": ev_id, "priority": priority},
                timeout=self._timeout,
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"status": "error", "message": str(exc)}

    def get_fleet(self) -> dict:
        try:
            r = requests.get(
                f"{self._base_url}/fleet",
                timeout=self._timeout,
                headers=self._headers,
            )
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            return {"fleet": [], "error": str(exc)}

    # ------------------------------------------------------------------
    # Stats (for debugging)
    # ------------------------------------------------------------------

    def fallback_count(self) -> int:
        return self._fallback_count
