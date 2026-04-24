from simp.organs.quantumarb.coinbase_connector import CoinbaseConnector
from simp.organs.quantumarb.exchange_connector import OrderSide, OrderStatus, OrderType


def test_coinbase_connector_exposes_fee_rate():
    sandbox = CoinbaseConnector(sandbox=True)
    live = CoinbaseConnector(sandbox=False)

    assert sandbox.get_fees() == 0.0
    assert live.get_fees() == 0.005


def test_coinbase_place_order_uses_created_order_id(monkeypatch):
    connector = CoinbaseConnector(sandbox=True)

    monkeypatch.setattr(
        connector,
        "_authenticated_request",
        lambda method, path, body=None: {
            "id": "cb-order-1",
            "product_id": "BTC-USD",
            "side": "buy",
            "type": "market",
            "status": "filled",
            "size": "0.001",
            "filled_size": "0.001",
            "executed_value": "65.0",
            "created_at": "2026-04-20T00:00:00Z",
        },
    )

    order = connector.place_order(
        symbol="BTC-USD",
        side=OrderSide.BUY,
        quantity=0.001,
        order_type=OrderType.MARKET,
    )

    assert order.order_id == "cb-order-1"
    assert order.symbol == "BTC-USD"
    assert order.status == OrderStatus.FILLED


def test_coinbase_cancel_order_accepts_list_response(monkeypatch):
    connector = CoinbaseConnector(sandbox=True)

    monkeypatch.setattr(
        connector,
        "_authenticated_request",
        lambda method, path, body=None: ["cb-order-2"],
    )

    assert connector.cancel_order("cb-order-2") is True
