import pandas as pd
import numpy as np
from agents.technical.indicators import rsi, macd, bollinger_bands, atr, obv


def extract_features(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows).set_index("time").sort_index()
    df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
    close = df["close"]

    features = pd.DataFrame(index=df.index)
    features["rsi"] = rsi(close)
    m = macd(close)
    features["macd_hist"] = m["histogram"]
    bb = bollinger_bands(close)
    bb_range = (bb["upper"] - bb["lower"]).replace(0, np.nan)
    features["bb_pct"] = (close - bb["lower"]) / bb_range
    features["atr"] = atr(df["high"], df["low"], close)
    obv_series = obv(close, df["volume"])
    features["obv_trend"] = obv_series.diff(5)
    features["mom_1"] = close.pct_change(1)
    features["mom_5"] = close.pct_change(5)
    features["mom_20"] = close.pct_change(20)
    avg_vol = df["volume"].rolling(20).mean().replace(0, np.nan)
    features["vol_ratio"] = df["volume"] / avg_vol

    return features.dropna()


def make_labels(close: pd.Series, threshold: float = 0.005) -> pd.Series:
    future_return = close.pct_change(1).shift(-1)
    labels = pd.Series(0, index=close.index, dtype=int)
    labels[future_return > threshold] = 1
    labels[future_return < -threshold] = -1
    return labels
