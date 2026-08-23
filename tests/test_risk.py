import pytest
from src.risk.risk_manager import RiskManager
from src.dnse.models import PlaceOrderRequest

def test_lot_size_validation():
    risk = RiskManager()
    # Odd lot (50 shares) -> Invalid
    invalid_order = PlaceOrderRequest(accountNo="123", symbol="SSI", side="NB", price=25000, quantity=50)
    valid, msg = risk.validate_order(invalid_order)
    assert not valid
    assert "bội số của 100" in msg

    # Round lot (100 shares) -> Valid
    valid_order = PlaceOrderRequest(accountNo="123", symbol="SSI", side="NB", price=25000, quantity=100)
    valid, _ = risk.validate_order(valid_order)
    assert valid

def test_max_order_value_validation():
    risk = RiskManager()
    risk.max_order_value = 100_000_000  # Max 100m VND

    # Order value = 300,000,000 > 100m -> Invalid
    huge_order = PlaceOrderRequest(accountNo="123", symbol="HPG", side="NB", price=30000, quantity=10000)
    valid, msg = risk.validate_order(huge_order)
    assert not valid
    assert "vượt quá ngưỡng cho phép" in msg

def test_circuit_breaker():
    risk = RiskManager()
    risk.max_daily_loss = 10_000_000
    risk.record_loss(15_000_000)  # Exceeded daily loss limit

    order = PlaceOrderRequest(accountNo="123", symbol="SSI", side="NB", price=25000, quantity=100)
    valid, msg = risk.validate_order(order)
    assert not valid
    assert "Đã chạm ngưỡng cắt lỗ" in msg
