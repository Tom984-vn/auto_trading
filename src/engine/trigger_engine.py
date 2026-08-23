import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from config.settings import settings
from src.utils.logger import app_logger
from src.dnse.models import MarketTick, PlaceOrderRequest

class TriggerEngine:
    """Bộ não so sánh điều kiện giá Realtime từ WebSocket với tập quy tắc rules.json"""

    def __init__(self, rules_file_path: Optional[str] = None):
        self.rules_file_path = Path(rules_file_path or settings.RULES_FILE_PATH)
        self.rules: List[Dict[str, Any]] = []
        self.triggered_rule_ids = set()
        self.load_rules()

    def load_rules(self):
        """Đọc và nạp các quy tắc giao dịch từ tệp rules.json"""
        if not self.rules_file_path.exists():
            app_logger.error(f"Tệp cấu hình quy tắc {self.rules_file_path} không tồn tại!")
            return

        try:
            with open(self.rules_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.rules = [r for r in data.get("rules", []) if r.get("active", True)]
            app_logger.info(f"Đã nạp {len(self.rules)} quy tắc giao dịch đang hoạt động từ rules.json")
        except Exception as e:
            app_logger.exception(f"Lỗi khi đọc tệp quy tắc rules.json: {e}")

    def get_subscribed_symbols(self) -> List[str]:
        """Lấy danh sách các mã cổ phiếu độc nhất cần đăng ký WebSocket"""
        return list(set(rule["symbol"] for rule in self.rules if "symbol" in rule))

    def evaluate_tick(self, tick: MarketTick) -> List[PlaceOrderRequest]:
        """Đánh giá giá tick vừa nhận được từ sàn với toàn bộ quy tắc"""
        matched_orders: List[PlaceOrderRequest] = []

        for rule in self.rules:
            rule_id = rule.get("id")
            if rule_id in self.triggered_rule_ids:
                continue  # Quy tắc đã được kích hoạt trước đó (One-shot)

            if rule.get("symbol") != tick.symbol:
                continue

            trigger_price = float(rule.get("trigger_price", 0))
            comparison = rule.get("comparison", "<=")
            current_price = tick.price

            is_triggered = False
            if comparison == "<=" and current_price <= trigger_price:
                is_triggered = True
            elif comparison == ">=" and current_price >= trigger_price:
                is_triggered = True
            elif comparison == "<" and current_price < trigger_price:
                is_triggered = True
            elif comparison == ">" and current_price > trigger_price:
                is_triggered = True

            if is_triggered:
                app_logger.success(
                    f"🔥 KÍCH HOẠT QUY TẮC [{rule_id}] cho {tick.symbol}! "
                    f"Giá hiện tại ({current_price:,.0f}) thỏa mãn điều kiện {comparison} {trigger_price:,.0f}"
                )
                self.triggered_rule_ids.add(rule_id)

                # Tạo request đặt lệnh
                order_req = PlaceOrderRequest(
                    accountNo=settings.DNSE_ACCOUNT_NO,
                    symbol=rule["symbol"],
                    side=rule["order_side"],
                    orderType=rule.get("order_type", "LO"),
                    price=float(rule.get("order_price", current_price)),
                    quantity=int(rule["quantity"]),
                    loanPackageId=settings.DNSE_LOAN_PACKAGE_ID,
                    marketId="UNDERLYING"
                )
                matched_orders.append(order_req)

        return matched_orders

    def reset_triggered_rules(self):
        """Reset danh sách các quy tắc đã kích hoạt"""
        self.triggered_rule_ids.clear()
        app_logger.info("Đã reset trạng thái kích hoạt quy tắc cho ngày mới.")
