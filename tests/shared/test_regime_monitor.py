import pytest
import numpy as np
from shared.regime_monitor import Regime, RegimeMonitor


def test_regime_monitor_expansion():
    rm = RegimeMonitor()
    assert rm.update_vix(15.0) == Regime.EXPANSION


def test_regime_monitor_crisis():
    rm = RegimeMonitor()
    assert rm.update_vix(35.0) == Regime.CRISIS


def test_regime_monitor_pandemic():
    rm = RegimeMonitor()
    assert rm.update_vix(55.0) == Regime.PANDEMIC


def test_regime_monitor_reset_daily():
    rm = RegimeMonitor()
    rm.update_vix(55.0)
    assert rm.get_regime() == Regime.PANDEMIC
    rm.reset_daily()
    assert all(not v for v in rm.hard_flags.values())


def test_hmm_detector_fallback_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr("shared.regime_monitor.RegimeMonitor.MODEL_PATH", str(tmp_path / "missing.pkl"))
    detector = RegimeMonitor()
    features = np.array([[15.0, 0.5, 0.5, 1.0]])
    probs = detector.predict_regime_probability(features)
    assert probs[Regime.EXPANSION] == pytest.approx(1.0)
    assert probs[Regime.CRISIS] == pytest.approx(0.0)
    assert probs[Regime.PANDEMIC] == pytest.approx(0.0)


def test_hmm_detector_fit_and_predict(tmp_path, monkeypatch):
    monkeypatch.setattr("shared.regime_monitor.RegimeMonitor.MODEL_PATH", str(tmp_path / "hmm.pkl"))
    detector = RegimeMonitor()

    np.random.seed(42)
    expansion = np.random.normal([15.0, 0.1, 0.5, 0.5], 0.5, (60, 4))
    crisis = np.random.normal([35.0, -0.5, -0.5, 2.0], 1.0, (30, 4))
    pandemic = np.random.normal([55.0, -2.0, -1.0, 4.0], 2.0, (10, 4))
    features = np.vstack([expansion, crisis, pandemic])

    detector.fit(features)
    probs = detector.predict_regime_probability(features)

    assert set(probs.keys()) <= set(Regime)
    total = sum(probs.values())
    assert total == pytest.approx(1.0, abs=0.01)
    assert all(0.0 <= v <= 1.0 for v in probs.values())


def test_hmm_detector_predict_regime_returns_regime(tmp_path, monkeypatch):
    monkeypatch.setattr("shared.regime_monitor.RegimeMonitor.MODEL_PATH", str(tmp_path / "hmm.pkl"))
    detector = RegimeMonitor()

    np.random.seed(0)
    expansion = np.random.normal([15.0, 0.1, 0.5, 0.5], 0.5, (60, 4))
    crisis = np.random.normal([35.0, -0.5, -0.5, 2.0], 1.0, (30, 4))
    pandemic = np.random.normal([55.0, -2.0, -1.0, 4.0], 2.0, (10, 4))
    features = np.vstack([expansion, crisis, pandemic])

    detector.fit(features)
    regime = detector.predict_regime(features)
    assert isinstance(regime, Regime)
