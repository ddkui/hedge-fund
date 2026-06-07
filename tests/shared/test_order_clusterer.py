import pytest
from datetime import datetime, timedelta
from shared.order_clusterer import OrderClusterer

def test_clusterer_batches_small_orders():
    """Test that clusterer batches small orders together."""
    clusterer = OrderClusterer(min_batch_value=10000)

    clusterer.add_order({"symbol": "AAPL", "qty": 10, "price": 150})
    clusterer.add_order({"symbol": "MSFT", "qty": 20, "price": 300})
    clusterer.add_order({"symbol": "GOOGL", "qty": 5, "price": 800})

    batch = clusterer.get_batch()

    assert batch is not None
    assert len(batch.orders) == 3
    assert batch.total_value == pytest.approx(11500, abs=100)
    assert batch.execution_time is None

def test_clusterer_holds_orders_below_threshold():
    """Test that clusterer waits if batch < min_value."""
    clusterer = OrderClusterer(min_batch_value=10000)

    clusterer.add_order({"symbol": "AAPL", "qty": 5, "price": 150})

    batch = clusterer.get_batch()

    assert batch is None

def test_clusterer_respects_time_limit():
    """Test that clusterer executes after max_hold_time."""
    clusterer = OrderClusterer(min_batch_value=50000, max_hold_seconds=5)

    clusterer.add_order({"symbol": "AAPL", "qty": 10, "price": 150})
    clusterer.orders[0]["added_at"] = datetime.now() - timedelta(seconds=6)

    batch = clusterer.get_batch()

    assert batch is not None
    assert "timeout" in batch.reason

def test_clusterer_filters_by_asset_class():
    """Test that clusterer doesn't mix stocks and crypto."""
    clusterer = OrderClusterer(min_batch_value=5000, allow_mixed_assets=False)

    clusterer.add_order({"symbol": "AAPL", "qty": 10, "price": 150, "asset_class": "stock"})
    clusterer.add_order({"symbol": "BTC", "qty": 0.1, "price": 40000, "asset_class": "crypto"})

    batch = clusterer.get_batch()

    assert len(batch.orders) == 1
    assert batch.orders[0]["symbol"] == "AAPL"

def test_clusterer_calculates_execution_cost_savings():
    """Test that clusterer calculates commission savings."""
    clusterer = OrderClusterer()

    savings = clusterer.calculate_savings(
        num_orders=3,
        commission_per_order=10,
        batch_commission=10
    )

    assert savings == 20
