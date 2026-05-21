import pandas as pd
import numpy as np


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss.where(avg_loss > 0, np.nan)
    rsi_val = 100 - (100 / (1 + rs))
    # When avg_loss == 0 (pure gains), RSI is 100
    return rsi_val.where(avg_loss != 0, 100.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    line = ema_fast - ema_slow
    signal_line = line.ewm(span=signal, adjust=False).mean()
    return {"line": line, "signal": signal_line, "histogram": line - signal_line}


def bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0) -> dict:
    middle = close.rolling(period).mean()
    std = close.rolling(period).std()
    return {"upper": middle + std_dev * std, "middle": middle, "lower": middle - std_dev * std}


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, min_periods=period).mean()


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(1)
    return (direction * volume).cumsum()


def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    typical_price = (high + low + close) / 3
    cum_vol = volume.cumsum()
    return (typical_price * volume).cumsum() / cum_vol.replace(0, np.nan)
