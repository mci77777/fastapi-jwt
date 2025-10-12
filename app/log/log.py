import logging
import sys

from loguru import logger as loguru_logger

from app.settings import settings


class InterceptHandler(logging.Handler):
    """将标准 logging 的日志转发到 loguru。"""

    def emit(self, record: logging.LogRecord) -> None:
        # 获取对应的 loguru level
        try:
            level = loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # 查找调用者的栈帧
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        loguru_logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


class Loggin:
    def __init__(self) -> None:
        debug = settings.debug
        if debug:
            self.level = "DEBUG"
        else:
            self.level = "INFO"

    def setup_logger(self):
        # 配置 loguru 输出到 stderr（避免与 uvicorn 的 stdout 冲突）
        loguru_logger.remove()
        loguru_logger.add(
            sink=sys.stderr,
            level=self.level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        )

        # 拦截标准 logging 的日志并转发到 loguru
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

        # 可选：添加文件日志
        # loguru_logger.add("logs/app.log", level=self.level, rotation="100 MB", retention="10 days")

        return loguru_logger


loggin = Loggin()
logger = loggin.setup_logger()
