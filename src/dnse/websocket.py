import asyncio
import json
from typing import List, Callable, Optional
import websockets
from config.settings import settings
from src.utils.logger import app_logger
from src.dnse.models import MarketTick

class DNSEWebSocketClient:
    """DNSE WebSocket Stream Receiver cho dữ liệu khớp lệnh Realtime 24/7"""

    def __init__(self, symbols: List[str], on_tick_callback: Callable[[MarketTick], None]):
        self.ws_url = settings.DNSE_WS_URL
        self.symbols = symbols
        self.on_tick_callback = on_tick_callback
        self._is_running = False
        self._ws: Optional[websockets.WebSocketClientProtocol] = None

    async def connect_and_listen(self):
        """Khởi tạo kết nối WebSocket với cơ chế Auto-Reconnect bền bỉ 24/7"""
        self._is_running = True
        retry_delay = 2  # giây khởi điểm cho backoff

        while self._is_running:
            try:
                app_logger.info(f"Đang kết nối DNSE WebSocket stream tại {self.ws_url}...")
                async with websockets.connect(
                    self.ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5
                ) as ws:
                    self._ws = ws
                    retry_delay = 2  # Reset delay sau khi kết nối thành công
                    app_logger.success("Kết nối WebSocket DNSE thành công!")

                    # Gửi tin nhắn Subscribe theo dõi các mã cổ phiếu
                    await self._subscribe_symbols(self.symbols)

                    # Lắng nghe dữ liệu đẩy về liên tục
                    async for message in ws:
                        if not self._is_running:
                            break
                        await self._handle_raw_message(message)

            except (websockets.ConnectionClosed, websockets.WebSocketException, OSError) as e:
                app_logger.warning(f"Mất kết nối DNSE WebSocket: {e}. Tự động kết nối lại sau {retry_delay} giây...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)  # Exponential backoff tối đa 60s
            except Exception as e:
                app_logger.exception(f"Lỗi không xác định trong WebSocket Stream: {e}")
                await asyncio.sleep(5)

    async def _subscribe_symbols(self, symbols: List[str]):
        """Đăng ký lắng nghe giá realtime cho danh sách cổ phiếu"""
        if not self._ws:
            return

        subscribe_payload = {
            "action": "subscribe",
            "channel": "market_tick",
            "symbols": symbols
        }
        await self._ws.send(json.dumps(subscribe_payload))
        app_logger.info(f"Đã gửi yêu cầu Subscribe dữ liệu giá realtime cho: {symbols}")

    async def _handle_raw_message(self, message: str):
        """Giải mã và chuyển đổi tin nhắn từ DNSE WebSocket thành MarketTick"""
        try:
            data = json.loads(message)
            # Kiểm tra định dạng tin nhắn tick khớp lệnh
            if data.get("type") == "tick" or "price" in data:
                symbol = data.get("symbol")
                price = float(data.get("price", 0))
                volume = int(data.get("volume", 0))
                timestamp = str(data.get("timestamp", ""))

                if symbol and price > 0:
                    tick = MarketTick(
                        symbol=symbol,
                        price=price,
                        volume=volume,
                        side=data.get("side"),
                        timestamp=timestamp
                    )
                    # Gọi callback xử lý tick ngay trên event loop
                    if asyncio.iscoroutinefunction(self.on_tick_callback):
                        await self.on_tick_callback(tick)
                    else:
                        self.on_tick_callback(tick)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            app_logger.error(f"Lỗi xử lý tin nhắn WebSocket: {e}")

    async def stop(self):
        """Đóng kết nối WebSocket an toàn"""
        self._is_running = False
        if self._ws:
            await self._ws.close()
            app_logger.info("Đã đóng kết nối DNSE WebSocket.")
