import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # DNSE Credentials & Endpoints
    DNSE_BASE_URL: str = Field(default="https://services.dnse.com.vn")
    DNSE_WS_URL: str = Field(default="wss://services.dnse.com.vn/ws")
    DNSE_USERNAME: str = Field(default="")
    DNSE_PASSWORD: str = Field(default="")
    DNSE_ACCOUNT_NO: str = Field(default="")
    DNSE_LOAN_PACKAGE_ID: int = Field(default=1531)

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_CHAT_ID: str = Field(default="")

    # Gmail Auto-OTP Configuration (100% Automated Auth)
    GMAIL_IMAP_SERVER: str = Field(default="imap.gmail.com")
    GMAIL_USER: str = Field(default="")
    GMAIL_APP_PASSWORD: str = Field(default="")
    USE_GMAIL_AUTO_OTP: bool = Field(default=True)

    # Risk Management Settings
    MAX_ORDER_VALUE: float = Field(default=500_000_000.0)  # Max VND per order
    MAX_DAILY_LOSS: float = Field(default=50_000_000.0)   # Max loss VND per day
    ENABLE_LIVE_TRADING: bool = Field(default=False)      # Live trading flag

    # App & Logging
    LOG_LEVEL: str = Field(default="INFO")
    RULES_FILE_PATH: str = Field(default=str(BASE_DIR / "config" / "rules.json"))

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
