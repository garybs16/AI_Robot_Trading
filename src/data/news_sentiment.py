"""News sentiment placeholder suitable for later vendor integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NewsSentiment:
    score: float
    source_count: int
    summary: str


class NewsSentimentProvider:
    def get_sentiment(self, symbol: str) -> NewsSentiment:
        return NewsSentiment(score=0.0, source_count=0, summary=f"No news provider configured for {symbol}")

