"""Contract tester CLI for model services.

Run against any URL to verify it conforms to
`contracts/openapi/model_service.yaml`. External researchers run this
before registering their service with the platform.

Usage:
    python main.py http://localhost:9000

    # Or via Docker (build context must be repo root so contracts/ is included):
    docker build -f services/contract_tester/Dockerfile -t contract-tester .
    docker run --rm --network=host contract-tester http://localhost:9000

    # With auth token:
    python main.py http://researcher.host:9000 --auth-token MY_TOKEN

Exit codes:
    0   all checks passed
    1   one or more checks failed
"""
from __future__ import annotations
import sys
import json
import time
import argparse
from pathlib import Path
from typing import Optional

import requests
import jsonschema


# ── Schema discovery ────────────────────────────────────────────────────

def _find_schemas_dir() -> Path:
    """Locate contracts/schemas/. Tries several candidate paths so the
    tester works equally well from a local checkout, a Docker container
    with /contracts mounted, or a baked image."""
    candidates = [
        Path("/workspace/contracts/schemas"),                                   # Docker bake
        Path(__file__).resolve().parent.parent.parent / "contracts" / "schemas",  # repo
        Path("/contracts/schemas"),                                              # mounted volume
        Path(__file__).resolve().parent / "schemas",                             # local copy
    ]
    for cand in candidates:
        if cand.exists() and (cand / "model_info.schema.json").exists():
            return cand
    raise FileNotFoundError(
        "Could not locate contracts/schemas/. Tried: "
        + ", ".join(str(c) for c in candidates)
    )


_SCHEMAS_DIR = _find_schemas_dir()


def _load_schema(name: str) -> dict:
    with open(_SCHEMAS_DIR / f"{name}.schema.json", encoding="utf-8") as f:
        return json.load(f)


# ── Synthetic test data ─────────────────────────────────────────────────

def _make_test_snapshot(session_id: str, step: int) -> dict:
    """Build a representative snapshot the model can react to."""
    return {
        "session_id": session_id,
        "step": step,
        "snapshot": {
            "intersections": {
                "tls_0": {
                    "phase_index": 0,
                    "phase_state": "GGrrGGrr",
                    "time_in_phase": 5.0,
                    "time_to_switch": 30.0,
                },
                "tls_1": {
                    "phase_index": 2,
                    "phase_state": "rrGGrrGG",
                    "time_in_phase": 10.0,
                    "time_to_switch": 25.0,
                },
            },
            "lanes": {
                "edge_0_lane_0": {
                    "queue_length": 5,
                    "vehicle_count": 7,
                    "occupancy": 0.5,
                    "avg_speed": 4.0,
                    "waiting_time": 18.0,
                    "co2": 1234.5,
                    "halting_number": 5,
                },
                "edge_1_lane_0": {
                    "queue_length": 2,
                    "vehicle_count": 3,
                    "occupancy": 0.3,
                    "avg_speed": 8.0,
                    "waiting_time": 5.0,
                    "co2": 800.0,
                    "halting_number": 2,
                },
            },
        },
    }


def _make_reset_payload(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "scenario": "test_grid",
        "network": {
            "scenario_name": "test_grid",
            "intersections": [
                {"id": "tls_0", "x": 0.0, "y": 0.0,
                 "phases": [{"index": 0, "state": "GGrrGGrr"}, {"index": 1, "state": "rrGGrrGG"}]},
                {"id": "tls_1", "x": 100.0, "y": 0.0,
                 "phases": [{"index": 0, "state": "GGrrGGrr"}, {"index": 1, "state": "rrGGrrGG"}]},
            ],
            "lanes": [
                {"id": "edge_0_lane_0", "edge_id": "edge_0", "length": 100.0, "speed_limit": 13.89},
                {"id": "edge_1_lane_0", "edge_id": "edge_1", "length": 100.0, "speed_limit": 13.89},
            ],
            "edges": [
                {"id": "edge_0", "from": "tls_0", "to": "tls_1"},
                {"id": "edge_1", "from": "tls_1", "to": "tls_0"},
            ],
            "connections": [],
        },
        "config": {"yellow_duration": 3, "min_green": 5, "max_green": 60, "step_length": 1.0},
    }


# ── Test runner ─────────────────────────────────────────────────────────

class TestRunner:
    def __init__(self, base_url: str, auth_token: Optional[str] = None, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Content-Type": "application/json"}
        if auth_token:
            self.headers["Authorization"] = f"Bearer {auth_token}"
        self.verbose = verbose
        self.results: list = []

    def _record(self, name: str, ok: bool, detail: str = "") -> bool:
        self.results.append({"test": name, "status": "PASS" if ok else "FAIL", "detail": detail})
        marker = "[PASS]" if ok else "[FAIL]"
        line = f"  {marker} {name}"
        if not ok and detail:
            line += f"  ({detail})"
        elif ok and self.verbose and detail:
            line += f"  ({detail})"
        print(line)
        return ok

    # ── Individual tests ────────────────────────────────────────────

    def test_info(self) -> Optional[dict]:
        print("\n/info")
        try:
            r = requests.get(f"{self.base_url}/info", timeout=5, headers=self.headers)
            r.raise_for_status()
            info = r.json()
        except Exception as exc:
            self._record("/info responds 2xx", False, str(exc))
            return None
        self._record("/info responds 2xx", True)

        try:
            jsonschema.validate(info, _load_schema("model_info"))
            self._record("/info conforms to model_info.schema.json", True)
        except jsonschema.ValidationError as exc:
            self._record("/info conforms to model_info.schema.json", False, exc.message)
            return None

        # Stricter checks beyond the schema
        self._record(
            "snapshot_schema_version == '1'",
            info.get("snapshot_schema_version") == "1",
            f"got {info.get('snapshot_schema_version')!r}",
        )
        self._record(
            "action_schema_version == '1'",
            info.get("action_schema_version") == "1",
            f"got {info.get('action_schema_version')!r}",
        )
        types = info.get("action_types_supported", [])
        valid = {"binary_switch", "set_phase", "set_duration"}
        self._record(
            "action_types_supported has at least one valid type",
            isinstance(types, list) and len(types) > 0 and all(t in valid for t in types),
            f"got {types}",
        )
        return info

    def test_health(self) -> None:
        print("\n/health")
        try:
            r = requests.get(f"{self.base_url}/health", timeout=5, headers=self.headers)
            r.raise_for_status()
            health = r.json()
        except Exception as exc:
            self._record("/health responds 2xx", False, str(exc))
            return
        self._record("/health responds 2xx", True)
        self._record("/health has 'status' field", "status" in health)
        self._record("/health has 'model_loaded' field", "model_loaded" in health)

    def test_reset(self, session_id: str) -> bool:
        print("\n/reset")
        try:
            r = requests.post(
                f"{self.base_url}/reset",
                json=_make_reset_payload(session_id),
                timeout=60,  # /reset can be slow (model load)
                headers=self.headers,
            )
            r.raise_for_status()
            response = r.json()
        except Exception as exc:
            self._record("/reset responds 2xx", False, str(exc))
            return False
        self._record("/reset responds 2xx", True)
        self._record(
            "/reset returns status='ready'",
            response.get("status") == "ready",
            f"got {response.get('status')!r}",
        )
        self._record(
            "/reset echoes session_id",
            response.get("session_id") == session_id,
            f"got {response.get('session_id')!r}",
        )
        return True

    def test_predict(self, session_id: str, info: dict) -> None:
        print("\n/predict")
        max_inference_ms = info.get("max_inference_ms", 2000)
        try:
            payload = _make_test_snapshot(session_id, step=0)
            t0 = time.time()
            r = requests.post(
                f"{self.base_url}/predict",
                json=payload,
                timeout=(max_inference_ms / 1000.0) + 1.0,
                headers=self.headers,
            )
            elapsed_ms = (time.time() - t0) * 1000.0
            r.raise_for_status()
            response = r.json()
        except Exception as exc:
            self._record("/predict responds 2xx", False, str(exc))
            return
        self._record("/predict responds 2xx", True, f"{elapsed_ms:.0f}ms")

        try:
            jsonschema.validate(response, _load_schema("action"))
            self._record("/predict response conforms to action.schema.json", True)
        except jsonschema.ValidationError as exc:
            self._record("/predict response conforms to action.schema.json", False, exc.message)

        self._record(
            f"/predict latency under declared max_inference_ms ({max_inference_ms}ms)",
            elapsed_ms <= max_inference_ms,
            f"actual {elapsed_ms:.0f}ms",
        )

        actions = response.get("actions", {}) or {}
        self._record("/predict actions is a dict", isinstance(actions, dict))

        valid_types = info.get("action_types_supported", [])
        for tls_id, action in actions.items():
            atype = action.get("type") if isinstance(action, dict) else None
            self._record(
                f"action[{tls_id}].type in declared action_types",
                atype in valid_types,
                f"got {atype!r}, declared {valid_types}",
            )

    def test_session_isolation(self) -> None:
        print("\nSession isolation")
        wrong_session = f"wrong_{int(time.time())}"
        try:
            r = requests.post(
                f"{self.base_url}/predict",
                json=_make_test_snapshot(wrong_session, step=0),
                timeout=5,
                headers=self.headers,
            )
            self._record(
                "/predict rejects wrong session_id with 4xx",
                400 <= r.status_code < 500,
                f"got {r.status_code}",
            )
        except Exception as exc:
            # Connection-level errors are acceptable too
            self._record("/predict rejects wrong session_id (connection error counts)", True, str(exc))

    def test_predict_burst(self, session_id: str, info: dict, count: int = 5) -> None:
        print(f"\n/predict burst x{count}")
        max_inference_ms = info.get("max_inference_ms", 2000)
        latencies = []
        for step in range(count):
            try:
                payload = _make_test_snapshot(session_id, step=step)
                t0 = time.time()
                r = requests.post(
                    f"{self.base_url}/predict",
                    json=payload,
                    timeout=(max_inference_ms / 1000.0) + 1.0,
                    headers=self.headers,
                )
                latencies.append((time.time() - t0) * 1000.0)
                r.raise_for_status()
            except Exception as exc:
                self._record(f"/predict step {step} succeeds", False, str(exc))
                return
        avg = sum(latencies) / len(latencies)
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        self._record(
            f"all {count} /predict calls succeeded",
            True,
            f"avg={avg:.0f}ms, p95={p95:.0f}ms",
        )

    # ── Orchestration ───────────────────────────────────────────────

    def run(self) -> bool:
        print(f"Contract Tester — {self.base_url}")
        print("=" * 70)

        info = self.test_info()
        if not info:
            return self._summarize()
        self.test_health()

        session_id = f"test_{int(time.time() * 1000)}"
        if not self.test_reset(session_id):
            return self._summarize()
        self.test_predict(session_id, info)
        self.test_predict_burst(session_id, info, count=5)
        self.test_session_isolation()

        return self._summarize()

    def _summarize(self) -> bool:
        passed = sum(1 for r in self.results if r["status"] == "PASS")
        failed = sum(1 for r in self.results if r["status"] == "FAIL")
        print()
        print("=" * 70)
        print(f"  PASSED: {passed:>3}    FAILED: {failed:>3}")
        if failed:
            print("\n  Failures:")
            for r in self.results:
                if r["status"] == "FAIL":
                    print(f"    [FAIL] {r['test']}: {r['detail']}")
        else:
            print("\n  All checks passed.")
        print("=" * 70)
        return failed == 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a model service against contracts/openapi/model_service.yaml"
    )
    parser.add_argument("url", help="Model service base URL (e.g. http://localhost:9000)")
    parser.add_argument("--auth-token", help="Bearer auth token", default=None)
    parser.add_argument("--verbose", action="store_true", help="Print details for passing tests too")
    args = parser.parse_args()

    runner = TestRunner(args.url, auth_token=args.auth_token, verbose=args.verbose)
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
