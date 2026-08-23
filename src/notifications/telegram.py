import asyncio
from typing import Optional, Callable
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from config.settings import settings
from src.utils.logger import app_logger

class TelegramNotificationService:
    """Telegram Notification Service & Interactive 2FA OTP Receiver"""

    def __init__(self, otp_callback: Optional[Callable[[str], bool]] = None):
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.otp_callback = otp_callback
        self.app: Optional[Application] = None
        self._is_running = False

    async def send_message(self, message: str) -> bool:
        """Gửi thông báo Markdown tới Telegram Chat"""
        if not self.bot_token or not self.chat_id:
            app_logger.warning("Telegram Bot Token hoặc Chat ID chưa cấu hình. Bỏ qua gửi tin nhắn.")
            return False

        try:
            if not self.app:
                self.app = Application.builder().token(self.bot_token).build()
                await self.app.initialize()

            await self.app.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="Markdown"
            )
            return True
        except Exception as e:
            app_logger.error(f"Thất bại khi gửi tin nhắn Telegram: {e}")
            return False

    async def request_otp(self):
        """Gửi tin nhắn chủ động nhắc người dùng nhập mã OTP 2FA"""
        msg = (
            "⚠️ **CẦN XÁC THỰC 2FA DNSE HÀNG NGÀY** ⚠️\n\n"
            "Vui lòng mở ứng dụng Entrade X (Smart OTP) hoặc lấy Email OTP, sau đó **nhập mã 6 chữ số** gửi lại trong chat này để kích hoạt giao dịch!"
        )
        await self.send_message(msg)

    async def _handle_otp_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Xử lý khi người dùng gõ tin nhắn chứa 6 chữ số OTP"""
        if not update.message or not update.message.text:
            return

        text = update.message.text.strip()
        # Kiểm tra nếu là chuỗi 6 chữ số
        if text.isdigit() and len(text) == 6:
            otp_code = text
            app_logger.info(f"Đã nhận mã OTP từ Telegram: {otp_code}")

            if self.otp_callback:
                success = self.otp_callback(otp_code)
                if success:
                    await update.message.reply_text("✅ **Xác thực OTP DNSE thành công!** Trading Token đã được cấp. Bot hoạt động bình thường.")
                else:
                    await update.message.reply_text("❌ **Xác thực OTP thất bại!** Vui lòng kiểm tra lại mã OTP và nhập lại.")
            else:
                await update.message.reply_text("ℹ️ Đã nhận OTP nhưng chưa gắn callback xác thực.")
        elif text.startswith("/otp "):
            otp_code = text.split(" ")[1].strip()
            if self.otp_callback and len(otp_code) == 6:
                success = self.otp_callback(otp_code)
                if success:
                    await update.message.reply_text("✅ **Xác thực OTP DNSE thành công!**")
                else:
                    await update.message.reply_text("❌ **Mã OTP không hợp lệ!**")

    async def start_polling(self):
        """Bắt đầu lắng nghe tin nhắn tương tác từ người dùng trên Telegram"""
        if not self.bot_token:
            app_logger.warning("Không có TELEGRAM_BOT_TOKEN. Tắt tính năng tương tác Telegram.")
            return

        try:
            if not self.app:
                self.app = Application.builder().token(self.bot_token).build()
                await self.app.initialize()

            self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self._handle_otp_message))
            self.app.add_handler(CommandHandler("otp", self._handle_otp_message))

            app_logger.info("Khởi chạy Telegram Polling Listener để nhận OTP...")
            await self.app.start()
            await self.app.updater.start_polling()
            self._is_running = True
        except Exception as e:
            app_logger.exception(f"Lỗi khởi chạy Telegram Polling: {e}")

    async def stop(self):
        """Dừng Telegram bot"""
        if self.app and self._is_running:
            await self.app.updater.stop()
            await self.app.stop()
            await self.app.shutdown()
            self._is_running = False
