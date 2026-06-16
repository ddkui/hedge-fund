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


def _make_ib_adapter_with_connected_ib():
    """Return an IBAdapter wired with a pre-connected mock IB instance."""
    from shared.brokers.ib import IBAdapter
    adapter = IBAdapter.__new__(IBAdapter)
    adapter.name = "ib-paper"
    adapter.config = {}
    adapter._host = "127.0.0.1"
    adapter._port = 7497
    adapter._client_id = 1

    trade_result = MagicMock()
    trade_result.orderStatus.status = "Filled"
    trade_result.orderStatus.avgFillPrice = 100.0

    mock_ib = MagicMock()
    mock_ib.isConnected.return_value = True
    mock_ib.placeOrder.return_value = trade_result
    adapter._ib = mock_ib
    return adapter, mock_ib


@pytest.mark.asyncio
async def test_ib_routes_option_asset_class():
    adapter, _ = _make_ib_adapter_with_connected_ib()
    trade = {
        "id": 1, "symbol": "AAPL", "action": "long", "quantity": 1.0,
        "asset_class": "option",
        "expiry": "20241220", "strike": 200.0, "right": "C",
    }
    with patch("asyncio.sleep", AsyncMock()), \
         patch("shared.brokers.ib.Option") as mock_cls:
        mock_cls.return_value = MagicMock()
        fill = await adapter.fill(trade)
    mock_cls.assert_called_once_with("AAPL", "20241220", 200.0, "C", exchange="SMART")
    assert fill.status == "filled"


@pytest.mark.asyncio
async def test_ib_routes_future_asset_class():
    adapter, _ = _make_ib_adapter_with_connected_ib()
    trade = {
        "id": 2, "symbol": "ES", "action": "long", "quantity": 1.0,
        "asset_class": "future",
        "expiry": "20241220", "exchange": "GLOBEX",
    }
    with patch("asyncio.sleep", AsyncMock()), \
         patch("shared.brokers.ib.Future") as mock_cls:
        mock_cls.return_value = MagicMock()
        fill = await adapter.fill(trade)
    mock_cls.assert_called_once_with("ES", "20241220", exchange="GLOBEX")
    assert fill.status == "filled"


@pytest.mark.asyncio
async def test_ib_routes_forex_asset_class():
    adapter, _ = _make_ib_adapter_with_connected_ib()
    trade = {
        "id": 3, "symbol": "EURUSD", "action": "long", "quantity": 10000.0,
        "asset_class": "forex",
    }
    with patch("asyncio.sleep", AsyncMock()), \
         patch("shared.brokers.ib.Forex") as mock_cls:
        mock_cls.return_value = MagicMock()
        fill = await adapter.fill(trade)
    mock_cls.assert_called_once_with("EURUSD")
    assert fill.status == "filled"


@pytest.mark.asyncio
async def test_ib_routes_bond_asset_class():
    adapter, _ = _make_ib_adapter_with_connected_ib()
    trade = {
        "id": 4, "symbol": "037833100", "action": "long", "quantity": 1.0,
        "asset_class": "bond",
    }
    with patch("asyncio.sleep", AsyncMock()), \
         patch("shared.brokers.ib.Bond") as mock_cls:
        mock_cls.return_value = MagicMock()
        fill = await adapter.fill(trade)
    mock_cls.assert_called_once_with(symbol="037833100")
    assert fill.status == "filled"


@pytest.mark.asyncio
async def test_ib_routes_cfd_asset_class():
    adapter, _ = _make_ib_adapter_with_connected_ib()
    trade = {
        "id": 5, "symbol": "AAPL", "action": "long", "quantity": 10.0,
        "asset_class": "cfd",
        "exchange": "SMART", "currency": "USD",
    }
    with patch("asyncio.sleep", AsyncMock()), \
         patch("shared.brokers.ib.CFD") as mock_cls:
        mock_cls.return_value = MagicMock()
        fill = await adapter.fill(trade)
    mock_cls.assert_called_once_with("AAPL", exchange="SMART", currency="USD")
    assert fill.status == "filled"


@pytest.mark.asyncio
async def test_ib_routes_crypto_by_asset_class():
    adapter, _ = _make_ib_adapter_with_connected_ib()
    trade = {
        "id": 6, "symbol": "BTCUSDT", "action": "long", "quantity": 0.1,
        "asset_class": "crypto",
    }
    with patch("asyncio.sleep", AsyncMock()), \
         patch("shared.brokers.ib.Crypto") as mock_cls:
        mock_cls.return_value = MagicMock()
        fill = await adapter.fill(trade)
    mock_cls.assert_called_once_with("BTC", "PAXOS", "USD")
    assert fill.status == "filled"


@pytest.mark.asyncio
async def test_ib_routes_stock_as_default():
    adapter, _ = _make_ib_adapter_with_connected_ib()
    trade = {
        "id": 7, "symbol": "TSLA", "action": "long", "quantity": 5.0,
        "asset_class": "stock",
    }
    with patch("asyncio.sleep", AsyncMock()), \
         patch("shared.brokers.ib.Stock") as mock_cls:
        mock_cls.return_value = MagicMock()
        fill = await adapter.fill(trade)
    mock_cls.assert_called_once_with("TSLA", "SMART", "USD")
    assert fill.status == "filled"
