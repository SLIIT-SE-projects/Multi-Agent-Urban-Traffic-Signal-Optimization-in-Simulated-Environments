"""ETA prediction wrapper around the TF/Keras LSTM model.

Wraps the same model as the in-process EVPSAdapter. Input: 10-frame
sequences with 6 features each:
  [speed, acceleration, distance_to_signal, queue_length, leader_gap, leader_speed]

Output: bounded ETA in seconds, normalized via the saved target_scaler.
"""
from __future__ import annotations
from typing import List
import pickle

import numpy as np
import pandas as pd
import tensorflow as tf


class EtaPredictor:
    FEATURE_COLS = [
        'speed', 'acceleration', 'distance_to_signal',
        'queue_length', 'leader_gap', 'leader_speed',
    ]

    def __init__(
        self,
        model_path: str,
        scaler_path: str,
        target_scaler_path: str,
        sequence_length: int = 10,
    ):
        self.sequence_length = sequence_length
        self.model = tf.keras.models.load_model(model_path)
        with open(scaler_path, "rb") as f:
            self.scaler = pickle.load(f)
        with open(target_scaler_path, "rb") as f:
            self.target_scaler = pickle.load(f)

    def predict(self, sequence: List[list], current_distance: float) -> float:
        """Predict ETA from a sequence of 10 feature frames.

        sequence: list of 10 lists of 6 floats
        current_distance: latest distance to next TLS (used for sanity bounds)
        Returns: ETA in seconds, bounded by physical constraints.
        """
        raw = np.array(sequence)
        scaled = np.zeros_like(raw)
        for i in range(len(raw)):
            step_df = pd.DataFrame([raw[i]], columns=self.FEATURE_COLS)
            scaled[i] = self.scaler.transform(step_df)[0]
        input_data = scaled.reshape(1, self.sequence_length, 6)
        normalized = self.model.predict(input_data, verbose=0)
        unscaled = float(self.target_scaler.inverse_transform(normalized.reshape(-1, 1))[0][0])

        # Physical sanity bounds (mirror evps_adapter.py)
        min_eta = max(0.0, current_distance / 25.0)        # ~max speed 25 m/s
        max_eta = max(10.0, (current_distance / 2.0) + 120.0)
        return max(min_eta, min(unscaled, max_eta))
