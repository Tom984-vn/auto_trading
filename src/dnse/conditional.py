import requests
from typing import Optional, List, Dict, Any
from config.settings import settings
from src.utils.logger import app_logger
from src.dnse.client import DNSEClient
from src.dnse.models import ConditionalOrderRequest, ConditionalOrderResponse

class DNSEConditionalOrderManager:
    """Quản lý các lệnh điều kiện (Server-Side Conditional Orders) trực tiếp trên sàn DNSE"""

    def __init__(self, dnse_client: DNSEClient):
        self.client = dnse_client
        self.endpoint = f"{settings.DNSE_BASE_URL.rstrip('/')}/conditional-order-api/v1/orders"

    def place_conditional_order(self, cond_req: ConditionalOrderRequest) -> Optional[ConditionalOrderResponse]:
        """Gửi lệnh điều kiện lên server DNSE (category: STOP cho Cắt lỗ / Chốt lời cứng)"""
        if not self.client.is_trading_token_valid():
            app_logger.error("Không thể đẩy lệnh điều kiện lên DNSE vì thiếu Trading Token!")
            return None

        if not settings.ENABLE_LIVE_TRADING:
            app_logger.warning(f"[DRY-RUN] Giả lập đẩy lệnh điều kiện Server DNSE cho {cond_req.symbol}: {cond_req.condition}")
            return ConditionalOrderResponse(
                id="DRY_COND_" + cond_req.symbol,
                symbol=cond_req.symbol,
                status="PENDING",
                condition=cond_req.condition
            )

        headers = {
            "Authorization": f"Bearer {self.client.trading_token}",
            "Content-Type": "application/json"
        }

        try:
            app_logger.info(f"Đang đẩy lệnh điều kiện Server DNSE: {cond_req.symbol} | Điều kiện: {cond_req.condition}")
            resp = self.client.session.post(
                self.endpoint,
                json=cond_req.model_dump(exclude_none=True),
                headers=headers,
                timeout=10
            )

            if resp.status_code in [200, 201]:
                data = resp.json()
                app_logger.success(f"Tạo lệnh điều kiện Server DNSE thành công! OrderID: {data.get('id')}")
                return ConditionalOrderResponse(
                    id=str(data.get("id")),
                    symbol=cond_req.symbol,
                    status=data.get("status", "ACTIVE"),
                    condition=cond_req.condition
                )
            else:
                app_logger.error(f"Lỗi tạo lệnh điều kiện DNSE! Code: {resp.status_code}, Resp: {resp.text}")
                return None
        except Exception as e:
            app_logger.exception(f"Ngoại lệ khi đẩy lệnh điều kiện Server DNSE: {e}")
            return None

    def get_active_conditional_orders(self) -> List[Dict[str, Any]]:
        """Lấy sổ lệnh điều kiện đang chờ kích hoạt trên DNSE"""
        if not self.client.is_jwt_valid():
            return []

        try:
            resp = self.client.session.get(self.endpoint, timeout=10)
            if resp.status_code == 200:
                return resp.json().get("data", [])
            return []
        except Exception as e:
            app_logger.error(f"Ngoại lệ khi lấy sổ lệnh điều kiện DNSE: {e}")
            return []
