# tests/shared/test_agent_params.py
import yaml


def test_load_returns_defaults_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from shared.agent_params import load_agent_params
    result = load_agent_params("nonexistent_agent", "expansion", {"threshold": 1.0})
    assert result == {"threshold": 1.0}


def test_load_returns_regime_params(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    params = {
        "news_momentum": {
            "_default": {"composite_threshold": 1.0},
            "expansion": {"composite_threshold": 0.8},
        }
    }
    (tmp_path / "agent_params.yaml").write_text(yaml.dump(params))
    from shared.agent_params import load_agent_params
    result = load_agent_params("news_momentum", "expansion", {"composite_threshold": 1.0})
    assert result["composite_threshold"] == 0.8


def test_load_falls_back_to_default_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    params = {"news_momentum": {"_default": {"composite_threshold": 1.5}}}
    (tmp_path / "agent_params.yaml").write_text(yaml.dump(params))
    from shared.agent_params import load_agent_params
    result = load_agent_params("news_momentum", "unknown_regime", {"composite_threshold": 1.0})
    assert result["composite_threshold"] == 1.5
