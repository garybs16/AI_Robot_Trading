"""Chronological model training helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.metrics import accuracy_score


@dataclass
class TrainedModel:
    model: object
    feature_columns: list[str]
    test_accuracy: float


class ModelTrainer:
    def __init__(self, model_type: str = "random_forest", random_state: int = 42) -> None:
        self.model_type = model_type
        self.random_state = random_state

    def _build_model(self):
        if self.model_type == "gradient_boosting":
            return GradientBoostingClassifier(random_state=self.random_state)
        return RandomForestClassifier(n_estimators=200, max_depth=5, random_state=self.random_state)

    def train(self, features: pd.DataFrame, labels: pd.Series, test_size: float = 0.25) -> TrainedModel:
        dataset = features.join(labels.rename("target"), how="inner").dropna()
        if len(dataset) < 50:
            raise ValueError("Not enough rows for chronological ML training")
        split = int(len(dataset) * (1 - test_size))
        train = dataset.iloc[:split]
        test = dataset.iloc[split:]
        model = self._build_model()
        columns = [col for col in dataset.columns if col != "target"]
        model.fit(train[columns], train["target"])
        accuracy = float(accuracy_score(test["target"], model.predict(test[columns]))) if len(test) else 0.0
        return TrainedModel(model=model, feature_columns=columns, test_accuracy=accuracy)

