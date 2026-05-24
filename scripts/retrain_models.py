#!/usr/bin/env python3
"""
Weekly ML model retraining pipeline.
Fetches latest price data, retrains GradientBoosting models for each symbol,
validates against holdout, deploys if performance improves.

Run manually or via cron: python scripts/retrain_models.py
"""
import asyncio
import sys
sys.path.insert(0, ".")
import pickle
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
from shared.db import Database
from shared.config import settings

MIN_ROWS = 50  # minimum price rows needed to retrain
MODEL_DIR = Path("models/weights")
MODEL_DIR.mkdir(parents=True, exist_ok=True)


async def fetch_training_data(db: Database, symbol: str, days: int = 90) -> list[dict]:
    rows = await db.fetch(
        f"""
        SELECT time, open, high, low, close, volume
        FROM prices
        WHERE symbol = $1 AND time > NOW() - INTERVAL '{days} days'
        ORDER BY time ASC
        """,
        symbol,
    )
    if len(rows) < MIN_ROWS:
        return []
    return rows


def build_features(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Build (X, y) arrays for GradientBoosting classification."""
    closes = np.array([float(r["close"]) for r in rows])
    volumes = np.array([float(r.get("volume") or 0) for r in rows])

    features = []
    labels = []
    window = 20

    for i in range(window, len(closes) - 1):
        window_slice = closes[i - window:i]
        ret = np.diff(window_slice) / window_slice[:-1]
        vol_slice = volumes[i - window:i]
        price_mean = window_slice.mean()
        price_std = window_slice.std() + 1e-9
        z_score = (closes[i] - price_mean) / price_std
        vol_ratio = volumes[i] / (vol_slice.mean() + 1e-9)

        feat = np.concatenate([
            ret[-10:],
            [z_score, vol_ratio, closes[i] / closes[i - 1] - 1],
        ])
        features.append(feat)
        # Label: 1 if next close > current close
        labels.append(1 if closes[i + 1] > closes[i] else 0)

    return np.array(features), np.array(labels)


async def retrain_symbol(db: Database, symbol: str) -> dict:
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import accuracy_score

    rows = await fetch_training_data(db, symbol)
    if not rows:
        print(f"  [{symbol}] skipped — insufficient data")
        return {"symbol": symbol, "status": "skipped", "accuracy": None}

    X, y = build_features(rows)
    if len(X) < 50:
        return {"symbol": symbol, "status": "skipped", "accuracy": None}

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    new_model = GradientBoostingClassifier(n_estimators=100, max_depth=3, random_state=42)
    new_model.fit(X_train, y_train)
    new_acc = accuracy_score(y_test, new_model.predict(X_test))

    model_path = MODEL_DIR / f"{symbol.lower()}_xgb.pkl"
    if model_path.exists():
        with open(model_path, "rb") as f:
            old_model = pickle.load(f)
        old_acc = accuracy_score(y_test, old_model.predict(X_test))
        if new_acc <= old_acc:
            print(f"  [{symbol}] new model ({new_acc:.3f}) not better than old ({old_acc:.3f}) — keeping old")
            return {"symbol": symbol, "status": "kept_old", "accuracy": old_acc}

    with open(model_path, "wb") as f:
        pickle.dump(new_model, f)

    print(f"  [{symbol}] deployed new model — accuracy: {new_acc:.3f}")
    return {"symbol": symbol, "status": "deployed", "accuracy": new_acc}


async def main():
    print(f"ML retraining started at {datetime.now(timezone.utc).isoformat()}")
    db = Database(settings.db_dsn)
    await db.connect()

    symbols = settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(",")
    results = []
    for sym in symbols:
        sym = sym.strip()
        print(f"Retraining {sym}...")
        result = await retrain_symbol(db, sym)
        results.append(result)

    await db.disconnect()

    deployed = [r for r in results if r["status"] == "deployed"]
    skipped = [r for r in results if r["status"] == "skipped"]
    print(f"\nRetraining complete. Deployed: {len(deployed)}, Skipped: {len(skipped)}")
    for r in deployed:
        print(f"  ✓ {r['symbol']} — accuracy {r['accuracy']:.3f}")


if __name__ == "__main__":
    asyncio.run(main())
