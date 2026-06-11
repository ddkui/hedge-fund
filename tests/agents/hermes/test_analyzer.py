import pytest
from agents.hermes.analyzer import compute_weight_proposals, apply_yaml_proposals
from agents.hermes.models import WeightProposal


def _row(agent="technical", regime="expansion", total=20, win_rate=0.50):
    wins = int(total * win_rate)
    return {"agent": agent, "regime": regime, "total": total, "wins": wins}


def _yaml():
    return {
        "_meta": {"last_updated": "2026-01-01T00:00:00Z"},
        "aggregator": {
            "_default": {"agent_weights": {"technical": 1.0, "sentiment": 1.0}},
            "expansion": {"agent_weights": {"technical": 1.0, "sentiment": 1.0}},
            "crisis": {"agent_weights": {"technical": 0.5, "sentiment": 1.5}},
        },
    }


# ── compute_weight_proposals ──────────────────────────────────────────────────

def test_no_proposal_in_neutral_range():
    assert compute_weight_proposals([_row(win_rate=0.55)], _yaml()) == []


def test_no_proposal_at_exact_low_boundary():
    # win_rate == 0.45 is in the neutral zone (< 0.45 is False)
    assert compute_weight_proposals([_row(win_rate=0.45)], _yaml()) == []


def test_increase_weight_for_high_performer():
    proposals = compute_weight_proposals([_row(win_rate=0.75)], _yaml())
    assert len(proposals) == 1
    assert proposals[0].proposed_weight > proposals[0].current_weight


def test_decrease_weight_for_poor_performer():
    proposals = compute_weight_proposals([_row(win_rate=0.30)], _yaml())
    assert len(proposals) == 1
    assert proposals[0].proposed_weight < proposals[0].current_weight


def test_skips_insufficient_samples():
    assert compute_weight_proposals([_row(total=5, win_rate=0.10)], _yaml()) == []


def test_skips_agent_not_in_yaml():
    assert compute_weight_proposals([_row(agent="ghost_agent", win_rate=0.10)], _yaml()) == []


def test_auto_apply_true_for_five_pct_change():
    # +5% change < 10% threshold → auto_apply
    proposals = compute_weight_proposals([_row(win_rate=0.75)], _yaml(), auto_threshold_pct=10.0)
    assert proposals[0].auto_apply is True


def test_auto_apply_false_when_threshold_equals_change():
    # 5% change is NOT < 5% → not auto_apply
    proposals = compute_weight_proposals([_row(win_rate=0.75)], _yaml(), auto_threshold_pct=5.0)
    assert proposals[0].auto_apply is False


def test_weight_capped_at_max():
    yaml_data = _yaml()
    yaml_data["aggregator"]["expansion"]["agent_weights"]["technical"] = 2.4
    proposals = compute_weight_proposals([_row(win_rate=0.75)], yaml_data)
    assert proposals[0].proposed_weight <= 2.5


def test_weight_floored_at_min():
    yaml_data = _yaml()
    yaml_data["aggregator"]["expansion"]["agent_weights"]["technical"] = 0.11
    proposals = compute_weight_proposals([_row(win_rate=0.20)], yaml_data)
    assert proposals[0].proposed_weight >= 0.1


# ── apply_yaml_proposals ──────────────────────────────────────────────────────

def test_applies_auto_proposal():
    yaml_data = _yaml()
    p = WeightProposal(
        agent_name="technical", regime="expansion",
        current_weight=1.0, proposed_weight=0.95,
        win_rate=0.40, total_signals=20, auto_apply=True,
    )
    apply_yaml_proposals(yaml_data, [p])
    assert yaml_data["aggregator"]["expansion"]["agent_weights"]["technical"] == 0.95


def test_skips_non_auto_proposal():
    yaml_data = _yaml()
    p = WeightProposal(
        agent_name="technical", regime="expansion",
        current_weight=1.0, proposed_weight=0.7,
        win_rate=0.25, total_signals=20, auto_apply=False,
    )
    apply_yaml_proposals(yaml_data, [p])
    assert yaml_data["aggregator"]["expansion"]["agent_weights"]["technical"] == 1.0


def test_updates_meta_timestamp():
    yaml_data = _yaml()
    old_ts = yaml_data["_meta"]["last_updated"]
    p = WeightProposal(
        agent_name="technical", regime="expansion",
        current_weight=1.0, proposed_weight=0.95,
        win_rate=0.40, total_signals=20, auto_apply=True,
    )
    apply_yaml_proposals(yaml_data, [p])
    assert yaml_data["_meta"]["last_updated"] != old_ts


def test_no_change_when_no_matching_regime_section():
    yaml_data = _yaml()
    p = WeightProposal(
        agent_name="technical", regime="stagflation",
        current_weight=1.0, proposed_weight=0.95,
        win_rate=0.40, total_signals=20, auto_apply=True,
    )
    apply_yaml_proposals(yaml_data, [p])
    # stagflation section doesn't exist → no KeyError, no change
    assert "stagflation" not in yaml_data["aggregator"]
