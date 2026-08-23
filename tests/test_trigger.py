import pytest
from src.engine.trigger_engine import TriggerEngine
from src.dnse.models import MarketTick

@pytest.fixture
def trigger_engine(tmp_path):
    rules_file = tmp_path / "rules.json"
    rules_content = """{
        "rules": [
            {
                "id": "RULE-TEST-001",
                "symbol": "SSI",
                "active": true,
                "condition_type": "STOP_LOSS",
                "trigger_price": 26500,
                "comparison": "<=",
                "order_side": "NS",
                "order_type": "LO",
                "order_price": 26400,
                "quantity": 100
            }
        ]
    }"""
    rules_file.write_text(rules_content, encoding="utf-8")
    return TriggerEngine(rules_file_path=str(rules_file))

def test_subscribed_symbols(trigger_engine):
    symbols = trigger_engine.get_subscribed_symbols()
    assert "SSI" in symbols

def test_evaluate_tick_triggered(trigger_engine):
    # SSI drops to 26450 <= 26500 -> Should trigger
    tick = MarketTick(symbol="SSI", price=26450, volume=1000, timestamp="10:00:00")
    orders = trigger_engine.evaluate_tick(tick)
    assert len(orders) == 1
    assert orders[0].symbol == "SSI"
    assert orders[0].side == "NS"
    assert orders[0].quantity == 100
    assert orders[0].price == 26400

def test_evaluate_tick_not_triggered(trigger_engine):
    # SSI is 27000 > 26500 -> Should not trigger
    tick = MarketTick(symbol="SSI", price=27000, volume=1000, timestamp="10:00:01")
    orders = trigger_engine.evaluate_tick(tick)
    assert len(orders) == 0

def test_one_shot_rule(trigger_engine):
    # SSI drops to 26450 -> Triggers 1st time
    tick1 = MarketTick(symbol="SSI", price=26450, volume=1000, timestamp="10:00:00")
    orders1 = trigger_engine.evaluate_tick(tick1)
    assert len(orders1) == 1

    # Next tick at 26400 -> Should not trigger again because rule is marked triggered
    tick2 = MarketTick(symbol="SSI", price=26400, volume=500, timestamp="10:00:02")
    orders2 = trigger_engine.evaluate_tick(tick2)
    assert len(orders2) == 0
