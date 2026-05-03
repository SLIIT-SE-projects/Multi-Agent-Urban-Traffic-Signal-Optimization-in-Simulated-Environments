"""Safety classification wrapper around the sklearn outcome model.

Decides whether granting a green wave at a junction is safe given:
- target queue length on the EV's lane
- conflicting volume on cross lanes
- time since last phase change (constant 10s in the original)
- number of conflicting lanes
- downstream lane length
- clearance distance heuristic

Returns 1 = UNSAFE (gridlock risk), 0 = SAFE.
"""
from __future__ import annotations
import pickle

import pandas as pd


class SafetyClassifier:
    FEATURE_COLS = [
        "target_queue_length",
        "conflicting_volume",
        "time_since_last_phase",
        "num_conflicting_lanes",
        "downstream_lane_length",
        "clearance_distance",
    ]

    def __init__(self, model_path: str):
        with open(model_path, "rb") as f:
            self.model = pickle.load(f)

    def predict(self, features: dict) -> int:
        df = pd.DataFrame(
            [[features[c] for c in self.FEATURE_COLS]],
            columns=self.FEATURE_COLS,
        )
        return int(self.model.predict(df)[0])
