import imaplib
import email
import re
import time
from typing import Optional
from config.settings import settings
from src.utils.logger import app_logger

class GmailOTPFetcher:
    """Tự động đọc mã OTP từ Gmail qua giao thức IMAP SSL 100% tự động"""

    def __init__(self):
        self.imap_server = settings.GMAIL_IMAP_SERVER
        self.email_address = settings.GMAIL_USER
        self.app_password = settings.GMAIL_APP_PASSWORD

    def fetch_latest_otp(self, timeout_seconds: int = 30, poll_interval: int = 3) -> Optional[str]:
        """Lắng nghe hộp thư đến Gmail và trích xuất mã OTP 6 chữ số từ DNSE"""
        if not self.email_address or not self.app_password:
            app_logger.error("Gmail User hoặc App Password chưa được thiết lập trong .env!")
            return None

        app_logger.info(f"Đang tự động đọc hộp thư Gmail ({self.email_address}) để tìm mã OTP DNSE...")
        start_time = time.time()

        while time.time() - start_time < timeout_seconds:
            try:
                # 1. Kết nối an toàn IMAP SSL
                mail = imaplib.IMAP4_SSL(self.imap_server)
                mail.login(self.email_address, self.app_password)
                mail.select("INBOX")

                # 2. Tìm kiếm email gần nhất từ DNSE hoặc chứa từ khóa OTP
                status, messages = mail.search(None, '(UNSEEN SUBJECT "OTP")')
                if status != "OK" or not messages[0]:
                    # Nếu chưa tìm thấy email UNSEEN, tìm email mới nhất có từ khóa DNSE
                    status, messages = mail.search(None, 'SUBJECT "DNSE"')

                if status == "OK" and messages[0]:
                    email_ids = messages[0].split()
                    latest_email_id = email_ids[-1]  # Lấy email mới nhất

                    status, data = mail.fetch(latest_email_id, "(RFC822)")
                    if status == "OK":
                        raw_email = data[0][1]
                        msg = email.message_from_bytes(raw_email)

                        # Giải mã nội dung email
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if content_type in ["text/plain", "text/html"]:
                                    part_payload = part.get_payload(decode=True)
                                    if part_payload:
                                        body += part_payload.decode("utf-8", errors="ignore")
                        else:
                            part_payload = msg.get_payload(decode=True)
                            if part_payload:
                                body = part_payload.decode("utf-8", errors="ignore")

                        # 3. Dùng Regular Expression tìm chuỗi 6 chữ số
                        otp_match = re.search(r'\b\d{6}\b', body)
                        if otp_match:
                            otp_code = otp_match.group(0)
                            app_logger.success(f"🎉 TỰ ĐỘNG BẮT ĐƯỢC MÃ OTP TỪ GMAIL: {otp_code}")
                            
                            # Đánh dấu email đã đọc và đóng kết nối
                            mail.store(latest_email_id, '+FLAGS', '\\Seen')
                            mail.logout()
                            return otp_code

                mail.logout()
            except Exception as e:
                app_logger.warning(f"Thử đọc Gmail chưa thành công: {e}. Thử lại sau {poll_interval}s...")

            time.sleep(poll_interval)

        app_logger.error(f"Hết thời gian chờ ({timeout_seconds}s) nhưng không tìm thấy email OTP từ DNSE trong Gmail.")
        return None
