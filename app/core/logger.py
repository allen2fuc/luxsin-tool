

import logging
from logging.handlers import RotatingFileHandler

def init_logger(
    level: int = logging.INFO,
    format: str = '%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s',
    datefmt: str = '%Y-%m-%d %H:%M:%S',

    # 滚动日志配置
    filename: str = "logs/app.log",
    maxBytes: int = 1024 * 1024 * 10,
    backupCount: int = 5,
    encoding: str = "utf-8",
) -> None:
    handler = RotatingFileHandler(filename, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding)
    handler.setFormatter(logging.Formatter(format, datefmt))
    handler.setLevel(level)

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter(format, datefmt))
    console.setLevel(level)
    
    logger = logging.getLogger()
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.addHandler(console)
    logger.setLevel(level)
    return None

