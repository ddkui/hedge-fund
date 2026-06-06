# tests/shared/test_broker_config.py
import pytest
import yaml


def _empty_yaml(tmp_path):
    p = tmp_path / "brokers.yaml"
    p.write_text(yaml.dump({"brokers": []}))
    return str(p)


def test_add_and_list_masks_secrets(tmp_path):
    from shared import broker_config as bc
    path = _empty_yaml(tmp_path)
    bc.add_broker({
        "name": "investor-john", "type": "alpaca",
        "api_key": "PKABCDEFGH1234", "secret_key": "secretXYZ9876",
        "paper": False,
    }, path=path)
    brokers = bc.list_brokers(path)
    assert len(brokers) == 1
    assert brokers[0]["name"] == "investor-john"
    # Secrets masked
    assert brokers[0]["api_key"] == "****1234"
    assert brokers[0]["secret_key"] == "****9876"
    assert brokers[0]["paper"] is False


def test_raw_file_keeps_full_secret(tmp_path):
    from shared import broker_config as bc
    path = _empty_yaml(tmp_path)
    bc.add_broker({
        "name": "x", "type": "alpaca",
        "api_key": "FULLKEY1234", "secret_key": "FULLSECRET9876", "paper": True,
    }, path=path)
    raw = yaml.safe_load(open(path).read())
    assert raw["brokers"][0]["api_key"] == "FULLKEY1234"


def test_add_rejects_duplicate_name(tmp_path):
    from shared import broker_config as bc
    path = _empty_yaml(tmp_path)
    bc.add_broker({"name": "dup", "type": "alpaca", "api_key": "k", "secret_key": "s", "paper": True}, path=path)
    with pytest.raises(ValueError):
        bc.add_broker({"name": "dup", "type": "alpaca", "api_key": "k2", "secret_key": "s2", "paper": True}, path=path)


def test_add_rejects_unknown_type(tmp_path):
    from shared import broker_config as bc
    path = _empty_yaml(tmp_path)
    with pytest.raises(ValueError):
        bc.add_broker({"name": "weird", "type": "robinhood"}, path=path)


def test_remove_broker(tmp_path):
    from shared import broker_config as bc
    path = _empty_yaml(tmp_path)
    bc.add_broker({"name": "gone", "type": "ib", "host": "127.0.0.1", "port": 7497, "client_id": 1}, path=path)
    assert bc.remove_broker("gone", path) is True
    assert bc.list_brokers(path) == []
    assert bc.remove_broker("gone", path) is False


def test_toggle_broker(tmp_path):
    from shared import broker_config as bc
    path = _empty_yaml(tmp_path)
    bc.add_broker({"name": "t", "type": "ib", "host": "127.0.0.1", "port": 7497, "client_id": 1}, path=path)
    assert bc.toggle_broker("t", False, path) is True
    assert bc.list_brokers(path)[0]["enabled"] is False
    assert bc.toggle_broker("missing", True, path) is False


def test_ib_account_no_secret_fields(tmp_path):
    from shared import broker_config as bc
    path = _empty_yaml(tmp_path)
    bc.add_broker({"name": "ib1", "type": "ib", "host": "127.0.0.1", "port": 7496, "client_id": 2}, path=path)
    b = bc.list_brokers(path)[0]
    assert b["port"] == 7496
    assert b["client_id"] == 2
