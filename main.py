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
        """Khởi tạo các lệnh Cắt lỗ cứng (Hard Stop Loss) lên server DNSE nếu chưa tồn tại"""
        app_logger.info("Đang kiểm tra và đồng bộ các lệnh điều kiện Server-Side lên DNSE...")
        
        for rule in self.trigger_engine.rules:
            if rule.get("server_side_stop", False):
                symbol = str(rule["symbol"]).upper()
                stop_price = float(rule["trigger_price"])
                side = str(rule["order_side"]).upper()

                # MUF 4: Kiểm tra xem lệnh điều kiện tương tự đã có trên sàn DNSE chưa
                if self.conditional_mgr.is_order_already_on_server(symbol, stop_price, side):
                    app_logger.info(f"Lệnh điều kiện Server-side [{symbol} | Stop: {stop_price:,.0f} | Side: {side}] ĐÃ TỒN TẠI trên DNSE. Bỏ qua không đặt trùng.")
                    continue

                # MUF 6: Khởi tạo payload chuẩn đặc tả DNSE Conditional Order API
                cond_req = ConditionalOrderRequest(
                    accountNo=settings.DNSE_ACCOUNT_NO,
                    symbol=symbol,
                    category="STOP",
                    condition=f"price {rule.get('comparison', '<=')} {stop_price}",
                    props=ConditionalOrderProps(
                        stopPrice=stop_price,
                        marketId="UNDERLYING"
                    ),
                    targetOrder=TargetOrder(
                        quantity=int(rule["quantity"]),
                        side=side,
                        price=float(rule.get("order_price", stop_price)),
                        orderType=str(rule.get("order_type", "LO")).upper(),
                        loanPackageId=settings.DNSE_LOAN_PACKAGE_ID
                    ),
                    timeInForce=TimeInForce(kind="GTD")
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
        
        # Khởi chạy Telegram Bot Listener # tìm cách tắt default telegram bot
        await self.telegram.start_polling()

        if login_success:
            await self.telegram.send_message(
                "🟢 **AUTO TRADING BOT ĐÃ KHỞI ĐỘNG TRÊN PROXMOX!**\n\n"
                "Đã đăng nhập Lớp 1 (JWT Token) thành công. Đang khởi chạy xác thực Lớp 2..."
            )

            # Kiểm tra nếu bật chế độ Gmail Auto-OTP (Tự động 100%)
            otp_verified = False
            if settings.USE_GMAIL_AUTO_OTP and settings.GMAIL_USER and settings.GMAIL_APP_PASSWORD:
                app_logger.info("Đang sử dụng chế độ Gmail Auto-OTP tự động 100%...")
                # Gửi yêu cầu DNSE bắn OTP về Email
                self.dnse_client.request_email_otp()

                from src.notifications.email_otp import GmailOTPFetcher
                fetcher = GmailOTPFetcher()
                # Chạy đọc Gmail không làm nghẽn event loop
                otp_code = await asyncio.to_thread(fetcher.fetch_latest_otp, 30, 3)
                
                if otp_code:
                    otp_verified = self._handle_otp_callback(otp_code)
                    if otp_verified:
                        await self.telegram.send_message(
                            f"🎉 **TỰ ĐỘNG XÁC THỰC OTP QUA GMAIL THÀNH CÔNG!**\n\n"
                            f"• Mã OTP: `{otp_code}`\n"
                            f"• Trạng thái: Trading Token đã sẵn sàng. Bot đang chạy tự động 100%."
                        )

            if not otp_verified:
                app_logger.warning("Chưa tự động xác thực được qua Gmail. Nhắc người dùng nhập OTP qua Telegram...")
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
