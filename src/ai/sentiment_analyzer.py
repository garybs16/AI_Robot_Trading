"""Simple sentiment normalization placeholder."""

from __future__ import annotations


class SentimentAnalyzer:
    def score_text(self, text: str) -> float:
        positive = {"beat", "growth", "upgrade", "profit", "bullish"}
        negative = {"miss", "lawsuit", "downgrade", "loss", "bearish"}
        words = {word.strip(".,!?").lower() for word in text.split()}
        return float(len(words & positive) - len(words & negative)) / max(len(words), 1)

