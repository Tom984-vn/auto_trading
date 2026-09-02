import requests
from typing import Optional, Dict, Any
from config.settings import settings
from src.utils.logger import app_logger
from src.dnse.models import (
    LoginRequest, LoginResponse, VerifyOTPRequest, VerifyOTPResponse,
    PlaceOrderRequest, PlaceOrderResponse
)

class DNSEClient:
    """DNSE LightSpeed REST API Client wrapper"""
    
    def __init__(self):
        self.base_url = settings.DNSE_BASE_URL.rstrip('/')
        self.jwt_token: Optional[str] = None
        self.trading_token: Optional[str] = None
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "DNSE-AutoTradingBot/1.0"
        })

    def is_jwt_valid(self) -> bool:
        return self.jwt_token is not None

    def is_trading_token_valid(self) -> bool:
        return self.trading_token is not None

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Lớp 1: Đăng nhập username/password để lấy jwt-token"""
        user = username or settings.DNSE_USERNAME
        pwd = password or settings.DNSE_PASSWORD

        if not user or not pwd:
            app_logger.error("DNSE username hoặc password chưa được thiết lập!")
            return False

        url = f"{self.base_url}/auth-service/v1/login"
        payload = {"username": user, "password": pwd}

        try:
            app_logger.info(f"Đang gửi yêu cầu đăng nhập DNSE cho tài khoản: {user}")
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.jwt_token = data.get("token") or data.get("jwtToken")
                self.session.headers["Authorization"] = f"Bearer {self.jwt_token}"
                app_logger.success("Đăng nhập lớp 1 (JWT Token) thành công!")
                return True
            else:
                app_logger.error(f"Đăng nhập DNSE thất bại! Status: {resp.status_code}, Body: {resp.text}")
                return False
        except Exception as e:
            app_logger.exception(f"Ngoại lệ khi gọi API đăng nhập DNSE: {e}")
            return False

    def request_email_otp(self) -> bool:
        """Yêu cầu DNSE gửi mã OTP xác thực về Email đăng ký"""
        if not self.is_jwt_valid():
            app_logger.error("Cần đăng nhập JWT Token thành công trước khi yêu cầu gửi Email OTP!")
            return False

        url = f"{self.base_url}/auth-service/v1/send-otp"
        payload = {"type": "EMAIL"}

        try:
            app_logger.info("Đang yêu cầu DNSE gửi mã OTP về Email...")
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code in [200, 201]:
                app_logger.success("Yêu cầu gửi Email OTP thành công! Đang chờ email về Gmail...")
                return True
            else:
                app_logger.warning(f"Gửi yêu cầu Email OTP: Code {resp.status_code}, Resp: {resp.text}")
                return False
        except Exception as e:
            app_logger.error(f"Ngoại lệ khi yêu cầu gửi Email OTP: {e}")
            return False

    def verify_otp(self, otp_code: str) -> bool:
        """Lớp 2: Gửi mã OTP thu được từ Telegram/User để lấy trading-token"""
        if not self.is_jwt_valid():
            app_logger.error("Cần đăng nhập thành công Lớp 1 trước khi xác thực OTP!")
            return False

        url = f"{self.base_url}/auth-service/v1/verify-otp"
        payload = {"otp": otp_code}

        try:
            app_logger.info("Đang xác thực OTP để lấy Trading Token...")
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.trading_token = data.get("tradingToken") or data.get("token")
                app_logger.success("Xác thực Lớp 2 thành công! Trading Token đã sẵn sàng giao dịch.")
                return True
            else:
                app_logger.error(f"Xác thực OTP thất bại! Status: {resp.status_code}, Body: {resp.text}")
                return False
        except Exception as e:
            app_logger.exception(f"Ngoại lệ khi xác thực OTP: {e}")
            return False



#Place real order here
    def place_order(self, order_req: PlaceOrderRequest) -> Optional[PlaceOrderResponse]:
        """Gửi lệnh mua/bán khớp trực tiếp trên chứng khoán cơ sở"""
        if not self.is_trading_token_valid():
            app_logger.error("Không thể đặt lệnh vì Trading Token 2FA chưa có hoặc đã hết hạn!")
            return None


#TRASH -----------------------------
        if not settings.ENABLE_LIVE_TRADING:
            app_logger.warning(f"[DRY-RUN / DRY TRADING] Giả lập đặt lệnh {order_req.side} {order_req.quantity} {order_req.symbol} @ {order_req.price} (Live trading disabled)")
            return PlaceOrderResponse(
                orderId="DRY_RUN_" + order_req.symbol,
                status="SUCCESS",
                message="Lệnh giả lập thành công (Dry-run)"
            )
#-----------------------------------
        url = f"{self.base_url}/order-service/v1/orders"
        headers = {
            "Authorization": f"Bearer {self.trading_token}"
        }

        try:
            app_logger.info(f"Đang gửi lệnh thật: {order_req.side} {order_req.quantity} {order_req.symbol} giá {order_req.price}")
            resp = self.session.post(url, json=order_req.model_dump(), headers=headers, timeout=10)
            if resp.status_code in [200, 201]:
                data = resp.json()
                app_logger.success(f"Đặt lệnh thành công! OrderID: {data.get('orderId')}")
                return PlaceOrderResponse(
                    orderId=str(data.get('orderId')),
                    status="SUCCESS",
                    message="Đặt lệnh thành công"
                )
            else:
                app_logger.error(f"Lỗi đặt lệnh! Status: {resp.status_code}, Resp: {resp.text}")
                return None
        except Exception as e:
            app_logger.exception(f"Ngoại lệ khi gọi API đặt lệnh: {e}")
            return None

    def get_account_portfolio(self, account_no: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Truy vấn danh mục tài sản chứng khoán cơ sở"""
        acc = account_no or settings.DNSE_ACCOUNT_NO
        if not self.jwt_token:
            app_logger.error("Chưa đăng nhập JWT Token!")
            return None

        url = f"{self.base_url}/user-service/v1/accounts/{acc}/portfolio"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
            return None
        except Exception as e:
            app_logger.error(f"Ngoại lệ khi lấy danh mục tài sản: {e}")
            return None
