# tests/shared/test_brokers.py
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from shared.brokers.base import BrokerFill, BrokerAdapter


def test_broker_fill_defaults_time():
    fill = BrokerFill(
        broker_name="test", trade_id=1, status="filled",
        fill_price=100.0, fill_qty=10.0, error_msg=None
    )
    assert fill.time.tzinfo is not None
    assert fill.broker_name == "test"
    assert fill.status == "filled"


def test_broker_adapter_is_abstract():
    with pytest.raises(TypeError):
        BrokerAdapter("test", {})  # type: ignore


@pytest.mark.asyncio
async def test_alpaca_adapter_fill_returns_broker_fill():
    from shared.brokers.alpaca import AlpacaAdapter
    adapter = AlpacaAdapter.__new__(AlpacaAdapter)
    adapter.name = "alpaca-paper"
    adapter.config = {}

    mock_order = MagicMock()
    mock_order.filled_avg_price = "185.50"
    mock_order.filled_qty = "10"

    mock_client = MagicMock()
    mock_client.submit_order = MagicMock(return_value=mock_order)
    adapter._client = mock_client

    trade = {"id": 1, "symbol": "AAPL", "action": "long",
             "quantity": 10.0, "asset_class": "stock"}
    fill = await adapter.fill(trade)
    assert fill.status == "filled"
    assert fill.fill_price == 185.50
    assert fill.broker_name == "alpaca-paper"


@pytest.mark.asyncio
async def test_alpaca_adapter_handles_rejection():
    from shared.brokers.alpaca import AlpacaAdapter
    adapter = AlpacaAdapter.__new__(AlpacaAdapter)
    adapter.name = "alpaca-paper"
    adapter.config = {}

    mock_client = MagicMock()
    mock_client.submit_order = MagicMock(side_effect=Exception("insufficient funds"))
    adapter._client = mock_client

    trade = {"id": 1, "symbol": "AAPL", "action": "long",
             "quantity": 10.0, "asset_class": "stock"}
    fill = await adapter.fill(trade)
    assert fill.status == "error"
    assert "insufficient funds" in fill.error_msg


@pytest.mark.asyncio
async def test_ib_adapter_unavailable_when_tws_down():
    from shared.brokers.ib import IBAdapter
    adapter = IBAdapter.__new__(IBAdapter)
    adapter.name = "ib-paper"
    adapter.config = {}
    adapter._host = "127.0.0.1"
    adapter._port = 7497
    adapter._client_id = 1

    mock_ib = MagicMock()
    mock_ib.isConnected = MagicMock(return_value=False)
    mock_ib.connectAsync = AsyncMock(side_effect=ConnectionRefusedError())
    adapter._ib = mock_ib

    available = await adapter.is_available()
    assert available is False


@pytest.mark.asyncio
async def test_ib_adapter_fill_returns_error_when_unavailable():
    from shared.brokers.ib import IBAdapter
    adapter = IBAdapter.__new__(IBAdapter)
    adapter.name = "ib-paper"
    adapter.config = {}
    adapter._host = "127.0.0.1"
    adapter._port = 7497
    adapter._client_id = 1

    mock_ib = MagicMock()
    mock_ib.isConnected = MagicMock(return_value=False)
    mock_ib.connectAsync = AsyncMock(side_effect=ConnectionRefusedError())
    adapter._ib = mock_ib

    trade = {"id": 1, "symbol": "AAPL", "action": "long",
             "quantity": 10.0, "asset_class": "stock"}
    fill = await adapter.fill(trade)
    assert fill.status == "error"
    assert fill.broker_name == "ib-paper"


def test_registry_loads_enabled_brokers(tmp_path):
    import yaml
    yaml_content = {
        "brokers": [
            {"name": "alpaca-test", "type": "alpaca", "api_key": "k",
             "secret_key": "s", "paper": True, "enabled": True},
            {"name": "disabled", "type": "alpaca", "api_key": "k",
             "secret_key": "s", "paper": True, "enabled": False},
        ]
    }
    config_file = tmp_path / "brokers.yaml"
    config_file.write_text(yaml.dump(yaml_content))

    from shared.brokers.registry import BrokerRegistry
    registry = BrokerRegistry(str(config_file)).load()
    brokers = registry.get_all()
    assert len(brokers) == 1
    assert brokers[0].name == "alpaca-test"


def test_registry_empty_when_no_file():
    from shared.brokers.registry import BrokerRegistry
    registry = BrokerRegistry("nonexistent.yaml").load()
    assert registry.get_all() == []
