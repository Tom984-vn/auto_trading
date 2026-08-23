import time
from typing import Dict, Tuple
from config.settings import settings
from src.utils.logger import app_logger
from src.dnse.models import PlaceOrderRequest

class RiskManager:
    """Đơn vị Quản trị rủi ro & Bảo vệ tài sản cho Auto Trading Bot"""

    def __init__(self):
        self.max_order_value = settings.MAX_ORDER_VALUE
        self.max_daily_loss = settings.MAX_DAILY_LOSS
        self.daily_realized_loss = 0.0
        self.recent_orders: Dict[str, float] = {}  # {symbol_side: timestamp}
        self.cooldown_seconds = 5.0                # Tránh trùng lệnh trong 5 giây

    def validate_order(self, order: PlaceOrderRequest) -> Tuple[bool, str]:
        """Kiểm tra toàn bộ các tiêu chí an toàn trước khi cho phép đặt lệnh"""
        
        # 1. Kiểm tra đơn vị lô (Phải là bội số của 100 đối với cổ phiếu cơ sở HOSE/HNX)
        if order.quantity <= 0 or order.quantity % 100 != 0:
            msg = f"Khối lượng đặt ({order.quantity}) không hợp lệ! Phải là lô tròn bội số của 100."
            app_logger.error(f"[RISK REJECT] {msg}")
            return False, msg

        # 2. Kiểm tra giá trị tối đa của một lệnh
        order_value = order.price * order.quantity
        if order_value > self.max_order_value:
            msg = f"Giá trị lệnh ({order_value:,.0f} VND) vượt quá ngưỡng cho phép tối đa ({self.max_order_value:,.0f} VND)!"
            app_logger.error(f"[RISK REJECT] {msg}")
            return False, msg

        # 3. Kiểm tra hạn mức lỗ tối đa trong ngày (Daily Circuit Breaker)
        if self.daily_realized_loss >= self.max_daily_loss:
            msg = f"Đã chạm ngưỡng cắt lỗ tối đa trong ngày ({self.daily_realized_loss:,.0f} / {self.max_daily_loss:,.0f} VND)! Tự động dừng giao dịch."
            app_logger.critical(f"[CIRCUIT BREAKER] {msg}")
            return False, msg

        # 4. Kiểm tra trùng lặp lệnh tần suất cao (Anti-duplicate / Idempotency)
        order_key = f"{order.symbol}_{order.side}"
        now = time.time()
        last_time = self.recent_orders.get(order_key, 0)
        if now - last_time < self.cooldown_seconds:
            msg = f"Lệnh trùng lặp quá nhanh cho {order_key}! Bỏ qua để tránh bắn trùng lệnh."
            app_logger.warning(f"[RISK REJECT] {msg}")
            return False, msg

        # Cập nhật thời gian đặt lệnh gần nhất
        self.recent_orders[order_key] = now
        app_logger.info(f"[RISK APPROVED] Lệnh {order.side} {order.quantity} {order.symbol} @ {order.price:,.0f} vượt qua kiểm tra an toàn.")
        return True, "APPROVED"

    def record_loss(self, loss_amount: float):
        """Ghi nhận khoản lỗ thực hiện trong ngày"""
        if loss_amount > 0:
            self.daily_realized_loss += loss_amount
            app_logger.warning(f"Cập nhật tổng lỗ trong ngày: {self.daily_realized_loss:,.0f} VND / {self.max_daily_loss:,.0f} VND")

    def reset_daily_loss(self):
        """Reset hạn mức lỗ vào đầu ngày giao dịch mới"""
        self.daily_realized_loss = 0.0
        self.recent_orders.clear()
        app_logger.info("Đã reset hạn mức rủi ro ngày mới thành công.")
