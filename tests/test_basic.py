import unittest
import json
import tempfile
from pathlib import Path
from src.dnse.models import PlaceOrderRequest, MarketTick
from src.risk.risk_manager import RiskManager
from src.engine.trigger_engine import TriggerEngine

class TestRiskManager(unittest.TestCase):
    def test_lot_size_validation(self):
        risk = RiskManager()
        # Odd lot (50 shares) -> Invalid
        invalid_order = PlaceOrderRequest(accountNo="123", symbol="SSI", side="NB", price=25000, quantity=50)
        valid, msg = risk.validate_order(invalid_order)
        self.assertFalse(valid)
        self.assertIn("bội số của 100", msg)

        # Round lot (100 shares) -> Valid
        valid_order = PlaceOrderRequest(accountNo="123", symbol="SSI", side="NB", price=25000, quantity=100)
        valid, _ = risk.validate_order(valid_order)
        self.assertTrue(valid)

    def test_max_order_value_validation(self):
        risk = RiskManager()
        risk.max_order_value = 100_000_000  # Max 100m VND

        # Order value = 300,000,000 > 100m -> Invalid
        huge_order = PlaceOrderRequest(accountNo="123", symbol="HPG", side="NB", price=30000, quantity=10000)
        valid, msg = risk.validate_order(huge_order)
        self.assertFalse(valid)
        self.assertIn("vượt quá ngưỡng cho phép", msg)

    def test_circuit_breaker(self):
        risk = RiskManager()
        risk.max_daily_loss = 10_000_000
        risk.record_loss(15_000_000)  # Exceeded daily loss limit

        order = PlaceOrderRequest(accountNo="123", symbol="SSI", side="NB", price=25000, quantity=100)
        valid, msg = risk.validate_order(order)
        self.assertFalse(valid)
        self.assertIn("Đã chạm ngưỡng cắt lỗ", msg)


class TestTriggerEngine(unittest.TestCase):
    def setUp(self):
        self.temp_file = tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8")
        rules_content = {
            "rules": [
                {
                    "id": "RULE-TEST-001",
                    "symbol": "SSI",
                    "active": True,
                    "condition_type": "STOP_LOSS",
                    "trigger_price": 26500,
                    "comparison": "<=",
                    "order_side": "NS",
                    "order_type": "LO",
                    "order_price": 26400,
                    "quantity": 100
                }
            ]
        }
        json.dump(rules_content, self.temp_file)
        self.temp_file.close()
        self.engine = TriggerEngine(rules_file_path=self.temp_file.name)

    def tearDown(self):
        Path(self.temp_file.name).unlink(missing_ok=True)

    def test_subscribed_symbols(self):
        symbols = self.engine.get_subscribed_symbols()
        self.assertIn("SSI", symbols)

    def test_evaluate_tick_triggered(self):
        tick = MarketTick(symbol="SSI", price=26450, volume=1000, timestamp="10:00:00")
        orders = self.engine.evaluate_tick(tick)
        self.assertEqual(len(orders), 1)
        self.assertEqual(orders[0].symbol, "SSI")
        self.assertEqual(orders[0].side, "NS")
        self.assertEqual(orders[0].quantity, 100)

    def test_one_shot_rule(self):
        tick1 = MarketTick(symbol="SSI", price=26450, volume=1000, timestamp="10:00:00")
        orders1 = self.engine.evaluate_tick(tick1)
        self.assertEqual(len(orders1), 1)

        tick2 = MarketTick(symbol="SSI", price=26400, volume=500, timestamp="10:00:02")
        orders2 = self.engine.evaluate_tick(tick2)
        self.assertEqual(len(orders2), 0)


if __name__ == "__main__":
    unittest.main()
