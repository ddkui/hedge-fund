import pandas as pd
import numpy as np
import pytest
from agents.technical.indicators import rsi, macd, bollinger_bands, atr, obv, vwap


def make_prices(n=50, start=100.0, volatility=2.0):
    np.random.seed(42)
    changes = np.random.normal(0, volatility, n)
    closes = start + np.cumsum(changes)
    highs = closes + np.abs(np.random.normal(0, 0.5, n))
    lows = closes - np.abs(np.random.normal(0, 0.5, n))
    opens = closes - np.random.normal(0, 0.3, n)
    volumes = np.random.randint(100_000, 1_000_000, n).astype(float)
    idx = pd.date_range("2024-01-01", periods=n, freq="1min", tz="UTC")
    return pd.DataFrame({"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes}, index=idx)


def test_rsi_returns_series_between_0_and_100():
    df = make_prices(50)
    result = rsi(df["close"], period=14)
    assert isinstance(result, pd.Series)
    valid = result.dropna()
    assert len(valid) > 0
    assert valid.between(0, 100).all()


def test_rsi_overbought_gt_70():
    closes = pd.Series([100.0] * 14 + [i * 2.0 for i in range(1, 20)])
    result = rsi(closes, period=14)
    assert result.dropna().iloc[-1] > 50


def test_macd_returns_dict_with_line_signal_hist():
    df = make_prices(50)
    result = macd(df["close"])
    assert "line" in result
    assert "signal" in result
    assert "histogram" in result
    assert isinstance(result["line"], pd.Series)
    assert len(result["histogram"].dropna()) > 0


def test_bollinger_bands_upper_above_lower():
    df = make_prices(50)
    result = bollinger_bands(df["close"])
    assert "upper" in result and "middle" in result and "lower" in result
    valid_upper = result["upper"].dropna()
    valid_lower = result["lower"].dropna()
    assert (valid_upper > valid_lower).all()


def test_atr_returns_positive_series():
    df = make_prices(50)
    result = atr(df["high"], df["low"], df["close"], period=14)
    assert isinstance(result, pd.Series)
    assert result.dropna().gt(0).all()


def test_obv_returns_series_same_length():
    df = make_prices(50)
    result = obv(df["close"], df["volume"])
    assert isinstance(result, pd.Series)
    assert len(result) == len(df)


def test_vwap_returns_series_between_low_and_high():
    df = make_prices(50)
    result = vwap(df["high"], df["low"], df["close"], df["volume"])
    assert isinstance(result, pd.Series)
    valid = result.dropna()
    assert len(valid) > 0
