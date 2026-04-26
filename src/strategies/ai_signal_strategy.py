"""AI signal strategy using chronological training and confidence gating."""

from __future__ import annotations

import pandas as pd

from ai.feature_engineering import make_features, make_labels
from ai.model_trainer import ModelTrainer
from ai.predictor import Predictor
from strategies.base_strategy import BaseStrategy, Signal, SignalAction


class AISignalStrategy(BaseStrategy):
    name = "ai_signal"

    def generate_signal(self, data: pd.DataFrame) -> Signal:
        horizon = int(self.params.get("prediction_horizon", 1))
        threshold = float(self.params.get("confidence_threshold", 0.60))
        min_rows = int(self.params.get("min_training_rows", 120))
        test_size = float(self.params.get("test_size", 0.25))
        model_type = str(self.params.get("model_type", "random_forest"))
        random_state = int(self.params.get("random_state", 42))

        if len(data) < min_rows:
            return Signal(SignalAction.HOLD, confidence=0.0, reason="not enough training rows")

        training_data = data.iloc[:-1].copy()
        latest_data = data.copy()
        try:
            features = make_features(training_data)
            labels = make_labels(training_data, horizon=horizon)
            trained = ModelTrainer(model_type, random_state).train(features, labels, test_size=test_size)
            prediction = Predictor(trained).predict_latest(make_features(latest_data))
        except Exception as exc:
            return Signal(SignalAction.HOLD, confidence=0.0, reason=f"AI model unavailable: {exc}")

        if prediction.confidence < threshold:
            return Signal(SignalAction.HOLD, confidence=prediction.confidence, reason="AI confidence below threshold")
        action = SignalAction.BUY if prediction.label == 1 else SignalAction.SELL
        return Signal(action, confidence=prediction.confidence, reason=f"AI signal {action.value}")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        horizon = int(self.params.get("prediction_horizon", 1))
        threshold = float(self.params.get("confidence_threshold", 0.60))
        min_rows = int(self.params.get("min_training_rows", 120))
        test_size = float(self.params.get("test_size", 0.25))
        model_type = str(self.params.get("model_type", "random_forest"))
        random_state = int(self.params.get("random_state", 42))

        signals = pd.Series(0, index=data.index, dtype=int)
        if len(data) < min_rows:
            return signals

        # Walk-forward retraining avoids fitting on future rows for each signal.
        for idx in range(min_rows, len(data)):
            window = data.iloc[:idx].copy()
            features = make_features(window)
            labels = make_labels(window, horizon=horizon)
            if len(features.join(labels.rename("target"), how="inner").dropna()) < min_rows // 2:
                continue
            try:
                trained = ModelTrainer(model_type, random_state).train(features, labels, test_size=test_size)
                prediction = Predictor(trained).predict_latest(make_features(data.iloc[: idx + 1]))
            except Exception:
                continue
            if prediction.confidence >= threshold:
                signals.iloc[idx] = 1 if prediction.label == 1 else -1
        return signals
