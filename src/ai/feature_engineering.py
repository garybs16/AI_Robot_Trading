"""Feature engineering for ML strategies without look-ahead bias."""

from __future__ import annotations

import pandas as pd

from utils.math_utils import bollinger_bands, rsi


def make_features(data: pd.DataFrame) -> pd.DataFrame:
    close = data["close"].astype(float)
    volume = data["volume"].astype(float)
    features = pd.DataFrame(index=data.index)
    features["return_1"] = close.pct_change()
    features["return_5"] = close.pct_change(5)
    features["volatility_10"] = features["return_1"].rolling(10).std()
    features["volume_change"] = volume.pct_change()
    features["rsi_14"] = rsi(close, 14)
    features["ma_10_ratio"] = close / close.rolling(10).mean() - 1
    features["ma_30_ratio"] = close / close.rolling(30).mean() - 1
    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    features["macd"] = ema_12 - ema_26
    middle, upper, lower = bollinger_bands(close, 20, 2)
    features["bb_position"] = (close - lower) / (upper - lower)
    features["high_low_range"] = (data["high"] - data["low"]) / close
    return features.replace([float("inf"), float("-inf")], pd.NA).dropna()


def make_labels(data: pd.DataFrame, horizon: int = 1) -> pd.Series:
    future_return = data["close"].pct_change(horizon).shift(-horizon)
    return (future_return > 0).astype(int)

