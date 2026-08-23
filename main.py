import asyncio
import signal
import sys
from config.settings import settings
from src.utils.logger import app_logger
from src.dnse.client import DNSEClient
from src.dnse.conditional import DNSEConditionalOrderManager
from src.risk.risk_manager import RiskManager
from src.engine.trigger_engine import TriggerEngine
from src.engine.executor import OrderExecutor
from src.dnse.websocket import DNSEWebSocketClient
from src.notifications.telegram import TelegramNotificationService
from src.dnse.models import MarketTick, ConditionalOrderRequest, ConditionalOrderProps, TargetOrder

class AutoTradingBot:
    def __init__(self):
        app_logger.info("Initializing DNSE Auto Trading Bot for Proxmox 24/7...")
        
        # 1. Base Components
        self.dnse_client = DNSEClient()
        self.risk_manager = RiskManager()
        self.trigger_engine = TriggerEngine()
        self.conditional_mgr = DNSEConditionalOrderManager(self.dnse_client)

        # 2. Telegram Notification & 2FA Handler
        self.telegram = TelegramNotificationService(otp_callback=self._handle_otp_callback)
        self.executor = OrderExecutor(self.dnse_client, self.risk_manager, self.telegram)

        # 3. WebSocket Client
        symbols = self.trigger_engine.get_subscribed_symbols()
        app_logger.info(f"Target underlying stock symbols: {symbols}")
        self.ws_client = DNSEWebSocketClient(symbols=symbols, on_tick_callback=self._on_market_tick)
        self._is_running = True

    def _handle_otp_callback(self, otp_code: str) -> bool:
        """Callback được gọi khi nhận mã OTP từ Telegram Bot"""
        success = self.dnse_client.verify_otp(otp_code)
        if success and settings.ENABLE_LIVE_TRADING:
            # Tự động đồng bộ các lệnh điều kiện Server-side cứng lên sàn DNSE
            self._sync_server_side_conditional_orders()
        return success

    def _sync_server_side_conditional_orders(self):
        """Khởi tạo các lệnh Cắt lỗ cứng (Hard Stop Loss) lên server DNSE"""
        app_logger.info("Đang đồng bộ các lệnh điều kiện Server-Side lên DNSE...")
        for rule in self.trigger_engine.rules:
            if rule.get("server_side_stop", False):
                cond_req = ConditionalOrderRequest(
                    accountNo=settings.DNSE_ACCOUNT_NO,
                    symbol=rule["symbol"],
                    category="STOP",
                    condition=f"price {rule.get('comparison', '<=')} {rule['trigger_price']}",
                    props=ConditionalOrderProps(
                        stopPrice=float(rule["trigger_price"]),
                        marketId="UNDERLYING"
                    ),
                    targetOrder=TargetOrder(
                        quantity=int(rule["quantity"]),
                        side=rule["order_side"],
                        price=float(rule.get("order_price", rule["trigger_price"])),
                        orderType=rule.get("order_type", "LO"),
                        loanPackageId=settings.DNSE_LOAN_PACKAGE_ID
                    )
                )
                self.conditional_mgr.place_conditional_order(cond_req)

    async def _on_market_tick(self, tick: MarketTick):
        """Xử lý mỗi khi có giá tick mới từ WebSocket"""
        matched_orders = self.trigger_engine.evaluate_tick(tick)
        for order in matched_orders:
            # Thực thi bắn lệnh không blocking
            asyncio.create_task(self.executor.process_and_execute(order))

    async def run(self):
        """Vòng lặp chính điều khiển Bot 24/7"""
        app_logger.info("Starting AutoTrading Bot event loop...")

        # Đăng nhập Lớp 1 (JWT)
        login_success = self.dnse_client.login()
        
        # Khởi chạy Telegram Bot Listener
        await self.telegram.start_polling()

        if login_success:
            await self.telegram.send_message(
                "🟢 **AUTO TRADING BOT ĐÃ KHỞI ĐỘNG TRÊN PROXMOX!**\n\n"
                "Đã đăng nhập Lớp 1 thành công. Đang chờ xác thực OTP Lớp 2..."
            )
            # Nhắc người dùng nhập OTP
            await self.telegram.request_otp()
        else:
            await self.telegram.send_message(
                "🔴 **LỖI KHỞI ĐỘNG BOT!** Đăng nhập DNSE thất bại. Vui lòng kiểm tra lại Username/Password trong file .env."
            )

        # Chạy kết nối WebSocket Stream không dừng
        ws_task = asyncio.create_task(self.ws_client.connect_and_listen())

        try:
            while self._is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            app_logger.info("Event loop cancelled.")
        finally:
            await self.shutdown()

    async def shutdown(self):
        """Tắt bot an toàn"""
        app_logger.info("Đang tắt bot an toàn...")
        self._is_running = False
        await self.ws_client.stop()
        await self.telegram.stop()
        app_logger.info("Bot đã dừng hẳn.")

def main():
    bot = AutoTradingBot()
    loop = asyncio.get_event_loop()

    def handle_sigterm():
        app_logger.info("Nhận tín hiệu SIGTERM/SIGINT. Đang dừng bot...")
        asyncio.create_task(bot.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handle_sigterm)
        except NotImplementedError:
            pass

    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        app_logger.info("Interrupted by user.")

if __name__ == "__main__":
    main()
