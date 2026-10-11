import logging
import os
from logging.handlers import RotatingFileHandler

def setup_logger(log_level="INFO", log_file="logs/podcast_sync.log",
                 max_bytes=10485760, backup_count=5):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger("podcast_sync")
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 文件 handler
    fh = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count,
        encoding="utf-8"
    )
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # 控制台 handler
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger
