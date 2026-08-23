import sys
from pathlib import Path
from loguru import logger
from config.settings import settings

LOG_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

def setup_logger():
    logger.remove()  # Remove default handler

    # Console Handler
    logger.add(
        sys.stdout,
        level=settings.LOG_LEVEL,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level:<=8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # Daily Rolling File Handler
    file_path = LOG_DIR / "auto_trading_{time:YYYY-MM-DD}.log"
    logger.add(
        str(file_path),
        level=settings.LOG_LEVEL,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<=8} | {name}:{function}:{line} - {message}",
        rotation="00:00",      # Rotate every midnight
        retention="30 days",   # Keep logs for 30 days
        compression="zip",     # Compress rotated logs
        encoding="utf-8"
    )

    return logger

app_logger = setup_logger()
