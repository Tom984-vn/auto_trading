# 📈 DNSE Auto Trading Bot (Chứng khoán Cơ sở 24/7 on Proxmox)

Hệ thống bot tự động đặt/hủy lệnh giao dịch chứng khoán cơ sở kết nối trực tiếp với **DNSE LightSpeed API**, chạy liên tục 24/7 trên máy server **Proxmox VE** (dưới dạng Docker Container).

---

## 🌟 Tính năng Nổi bật

1. **Xác thực 2FA Tương tác qua Telegram Bot:**
   - Đăng nhập Lớp 1 (JWT) tự động.
   - Nhắc nhở người dùng nhập mã Smart OTP/Email OTP 6 chữ số trực tiếp qua ứng dụng Telegram trên điện thoại để lấy `trading-token`.
2. **Giao dịch Chứng khoán Cơ sở (`UNDERLYING`):**
   - Đặt lệnh mua/bán khớp trực tiếp trên thị trường cổ phiếu (HOSE, HNX, UPCoM).
   - Kiểm tra lô tròn (bội số 100).
3. **Mô hình Quản lý Lệnh Điều kiện Hybrid 2 Lớp:**
   - **Local WebSocket Trigger:** Lắng nghe tick giá realtime từng millisecond để kích hoạt chiến lược động (Stop Loss, Take Profit, Breakout).
   - **DNSE Server Conditional Order:** Tự động đồng bộ các lệnh Cắt lỗ cứng (Hard Stop Loss) lên server DNSE (`POST /conditional-order-api/v1/orders`). Đảm bảo cắt lỗ an toàn ngay cả khi Proxmox sập nguồn hoặc rớt mạng.
4. **Bộ lọc Quản trị Rủi ro (Risk Manager):**
   - Giới hạn vốn tối đa trên mỗi lệnh (`MAX_ORDER_VALUE`).
   - Ngắt mạch tự động khi chạm mức lỗ tối đa trong ngày (`MAX_DAILY_LOSS`).
   - Chống bắn trùng lệnh tần suất cao (Anti-duplicate / Idempotency).
5. **Vận hành Bền bỉ 24/7 trên Proxmox:**
   - Tự động kết nối lại WebSocket stream (Exponential backoff).
   - Đóng gói Docker Container nhẹ (`python:3.11-slim`), tự động chạy lại khi khởi động máy (`restart: always`).

---

## 📁 Cấu trúc Dự án

```
auto_trading/
├── config/
│   ├── settings.py          # Quản lý môi trường với Pydantic
│   └── rules.json           # Danh sách các quy tắc & lệnh điều kiện
├── src/
│   ├── dnse/
│   │   ├── client.py        # DNSE REST API Client
│   │   ├── conditional.py   # DNSE Server Conditional Order API
│   │   ├── websocket.py     # WebSocket Client realtime tick stream
│   │   └── models.py        # Pydantic data schemas
│   ├── engine/
│   │   ├── trigger_engine.py # Đánh giá quy tắc điều kiện giá local
│   │   └── executor.py       # Thực thi bắn lệnh & gửi alert Telegram
│   ├── risk/
│   │   └── risk_manager.py   # Kiểm tra hạn mức & quy tắc an toàn
│   ├── notifications/
│   │   └── telegram.py      # Gửi thông báo & nhận mã OTP
│   └── utils/
│       └── logger.py        # Loguru ghi log ngày xoay vòng
├── tests/                   # Pytest unit tests
├── main.py                  # Điểm khởi chạy chính
├── Dockerfile               # File đóng gói container
├── docker-compose.yml       # Production deployment script
├── .env.example             # Mẫu biến môi trường
└── README.md                # Hướng dẫn sử dụng
```

---

## 🚀 Hướng dẫn Triển khai trên Proxmox 24/7

### 1. Khởi tạo File Cấu hình `.env`
Sao chép mẫu cấu hình từ `.env.example`:
```bash
cp .env.example .env
```
Điền các thông tin tài khoản DNSE và Telegram Bot Token:
```env
DNSE_USERNAME=0001XXXXXX
DNSE_PASSWORD=your_password
DNSE_ACCOUNT_NO=0001XXXXXX

TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
TELEGRAM_CHAT_ID=123456789

ENABLE_LIVE_TRADING=false  # Chế độ thử nghiệm Dry-run (mặc định false). Đổi true khi chạy thật.
```

### 2. Cấu hình Quy tắc Lệnh Điều kiện `config/rules.json`
Tệp `config/rules.json` định nghĩa các mã cổ phiếu và điều kiện kích hoạt:
```json
{
  "rules": [
    {
      "id": "RULE-SSI-001",
      "symbol": "SSI",
      "active": true,
      "condition_type": "STOP_LOSS",
      "trigger_price": 26500,
      "comparison": "<=",
      "order_side": "NS",
      "order_type": "LO",
      "order_price": 26400,
      "quantity": 1000,
      "server_side_stop": true,
      "description": "Cắt lỗ SSI khi giá <= 26.500 VND"
    }
  ]
}
```
*   `server_side_stop: true`: Đẩy lệnh cắt lỗ trực tiếp lên server sàn DNSE.

---

### 3. Triển khai Docker trên Proxmox VE (VM hoặc LXC Container)

#### Cách 1: Sử dụng Docker Compose (Khuyên dùng)
```bash
# Clone hoặc chép thư mục dự án lên Proxmox
cd /root/auto_trading

# Khởi chạy container ngầm 24/7
docker-compose up -d --build
```

#### Kiểm tra Trạng thái Container & Log:
```bash
# Xem log realtime
docker-compose logs -f

# Kiểm tra container đang chạy
docker ps
```

---

## 📱 Quy trình Xác thực OTP 2FA Hàng Ngày

1. Khi bot khởi chạy (hoặc mỗi sáng khi bắt đầu phiên làm việc), bot sẽ tự động gọi API đăng nhập Lớp 1 (JWT Token).
2. Bot gửi 1 tin nhắn thông báo về Telegram của bạn:
   > ⚠️ **CẦN XÁC THỰC 2FA DNSE HÀNG NGÀY**
   > Vui lòng mở ứng dụng Entrade X (Smart OTP) hoặc lấy Email OTP, sau đó **nhập mã 6 chữ số** gửi lại trong chat này.
3. Bạn mở app Entrade X lấy mã OTP (ví dụ: `849201`) và **gõ thẳng `849201` vào khung chat Telegram**.
4. Bot tự động bắt mã OTP, gửi lên DNSE lấy `trading-token` và báo lại:
   > ✅ **Xác thực OTP DNSE thành công!** Trading Token đã được cấp. Bot hoạt động bình thường.

---

## 🧪 Chạy Kiểm thử Unit Tests

Nếu bạn muốn chạy thử nghiệm các bài test logic ở môi trường phát triển:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/
```

---

## ⚠️ Lưu ý Quản trị Rủi ro Khi Giao dịch Thật

1. Mặc định `ENABLE_LIVE_TRADING=false` trong file `.env`. Trong chế độ này, bot sẽ chạy giả lập (Dry-run), ghi log và gửi tin nhắn Telegram mô phỏng để bạn kiểm tra luồng mà không phát sinh lệnh thật.
2. Trước khi chuyển `ENABLE_LIVE_TRADING=true`, hãy chắc chắn rằng bạn đã đặt hạn mức `MAX_ORDER_VALUE` và `MAX_DAILY_LOSS` phù hợp với quy mô tài sản của mình.
