from agents.macro.regime import classify_regime, MacroRegime, FedCycle


def make_macro(fedfunds=5.33, cpi=3.2, unrate=3.8, dgs10=4.2, gdp=2.1, prev_fedfunds=4.0):
    return {
        "FEDFUNDS": fedfunds,
        "CPIAUCSL": cpi,
        "UNRATE": unrate,
        "DGS10": dgs10,
        "GDP": gdp,
        "FEDFUNDS_PREV": prev_fedfunds,
    }


def test_expansion_regime():
    data = make_macro(fedfunds=5.0, cpi=2.5, unrate=3.8, gdp=2.5, prev_fedfunds=4.5)
    result = classify_regime(data)
    assert result.regime == MacroRegime.EXPANSION


def test_stagflation_regime():
    data = make_macro(fedfunds=5.5, cpi=7.5, unrate=4.5, gdp=0.5, prev_fedfunds=4.0)
    result = classify_regime(data)
    assert result.regime == MacroRegime.STAGFLATION


def test_contraction_regime():
    data = make_macro(fedfunds=2.0, cpi=1.5, unrate=6.5, gdp=-1.0, prev_fedfunds=3.0)
    result = classify_regime(data)
    assert result.regime == MacroRegime.CONTRACTION


def test_hiking_cycle():
    data = make_macro(fedfunds=5.5, prev_fedfunds=4.5)
    result = classify_regime(data)
    assert result.fed_cycle == FedCycle.HIKING


def test_cutting_cycle():
    data = make_macro(fedfunds=4.0, prev_fedfunds=5.25)
    result = classify_regime(data)
    assert result.fed_cycle == FedCycle.CUTTING


def test_yield_curve_inverted():
    data = make_macro(fedfunds=5.5, dgs10=4.2)
    result = classify_regime(data)
    assert result.yield_curve_inverted is True


def test_yield_curve_normal():
    data = make_macro(fedfunds=2.0, dgs10=4.5)
    result = classify_regime(data)
    assert result.yield_curve_inverted is False


def test_risk_on_in_expansion():
    data = make_macro(fedfunds=3.0, cpi=2.0, unrate=3.5, gdp=3.0, prev_fedfunds=2.5)
    result = classify_regime(data)
    assert result.risk_on is True
