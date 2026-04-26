"""Prediction wrapper with confidence scores."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ai.model_trainer import TrainedModel


@dataclass(frozen=True)
class Prediction:
    label: int
    confidence: float


class Predictor:
    def __init__(self, trained_model: TrainedModel) -> None:
        self.trained_model = trained_model

    def predict_latest(self, features: pd.DataFrame) -> Prediction:
        row = features[self.trained_model.feature_columns].iloc[[-1]]
        model = self.trained_model.model
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(row)[0]
            label = int(proba.argmax())
            confidence = float(proba[label])
            return Prediction(label=label, confidence=confidence)
        label = int(model.predict(row)[0])
        return Prediction(label=label, confidence=1.0)

