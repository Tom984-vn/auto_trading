import asyncio
from typing import Optional
from src.dnse.client import DNSEClient
from src.risk.risk_manager import RiskManager
from src.notifications.telegram import TelegramNotificationService
from src.dnse.models import PlaceOrderRequest
from src.utils.logger import app_logger

class OrderExecutor:
    """Đơn vị điều phối xử lý kiểm tra rủi ro, thực thi đặt lệnh và phát thông báo Telegram"""

    def __init__(
        self,
        dnse_client: DNSEClient,
        risk_manager: RiskManager,
        telegram_service: Optional[TelegramNotificationService] = None
    ):
        self.client = dnse_client
        self.risk_manager = risk_manager
        self.telegram = telegram_service

    async def process_and_execute(self, order: PlaceOrderRequest) -> bool:
        """Kiểm tra quy tắc an toàn rủi ro và thực thi đặt lệnh chứng khoán cơ sở"""
        app_logger.info(f"Đang chuẩn bị xử lý lệnh: {order.side} {order.quantity} {order.symbol} @ {order.price:,.0f}")

        # 1. Kiểm tra qua bộ lọc Risk Manager
        is_valid, reason = self.risk_manager.validate_order(order)
        if not is_valid:
            app_logger.warning(f"Lệnh bị hủy bởi Risk Manager! Lý do: {reason}")
            if self.telegram:
                await self.telegram.send_message(
                    f"⚠️ **LỆNH BỊ TỪ CHỐI BỞI RISK MANAGER**\n\n"
                    f"• Mã: `{order.symbol}` | Chiều: `{order.side}`\n"
                    f"• Khối lượng: `{order.quantity:,}` | Giá: `{order.price:,.0f}`\n"
                    f"• Lý do: {reason}"
                )
            return False

        # 2. Thực thi gửi lệnh qua DNSE REST API
        resp = self.client.place_order(order)
        if resp and resp.status == "SUCCESS":
            msg = (
                f"🚀 **ĐẶT LỆNH BẮN THÀNH CÔNG!**\n\n"
                f"• Mã cổ phiếu: `{order.symbol}`\n"
                f"• Loại lệnh: `{order.orderType}` | Chiều: `{order.side}`\n"
                f"• Khối lượng: `{order.quantity:,}` CP\n"
                f"• Giá đặt: `{order.price:,.0f}` VND\n"
                f"• OrderID: `{resp.orderId}`\n"
                f"• Ghi chú: {resp.message}"
            )
            app_logger.success(f"Đặt lệnh thành công cho {order.symbol}. OrderID: {resp.orderId}")
            if self.telegram:
                await self.telegram.send_message(msg)
            return True
        else:
            msg = (
                f"❌ **ĐẶT LỆNH THẤT BẠI ON DNSE!**\n\n"
                f"• Mã cổ phiếu: `{order.symbol}` | Chiều: `{order.side}`\n"
                f"• Vui lòng kiểm tra lại trạng thái tài khoản hoặc kết nối API!"
            )
            app_logger.error(f"Gửi lệnh thất bại tới DNSE cho {order.symbol}")
            if self.telegram:
                await self.telegram.send_message(msg)
            return False
