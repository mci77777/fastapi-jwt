"""日志收集服务，收集后端 Python logger 输出。"""
from __future__ import annotations

import logging
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LogHandler(logging.Handler):
    """自定义日志处理器，将日志写入内存队列。"""

    def __init__(self, logs_deque: deque) -> None:
        super().__init__()
        self.logs = logs_deque

    def emit(self, record: logging.LogRecord) -> None:
        """处理日志记录。

        Args:
            record: 日志记录对象
        """
        try:
            self.logs.append(
                {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "level_num": record.levelno,
                    "user_id": getattr(record, "user_id", None),
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
            )
        except Exception:
            # 避免日志处理器本身抛出异常
            self.handleError(record)


class LogCollector:
    """日志收集器，管理内存队列并提供查询接口。"""

    def __init__(self, max_size: int = 100) -> None:
        """初始化日志收集器。

        Args:
            max_size: 最大日志条数（超出后自动丢弃最旧的）
        """
        self.logs: deque = deque(maxlen=max_size)
        self.handler = LogHandler(self.logs)
        self.handler.setLevel(logging.WARNING)  # 只收集 WARNING 及以上级别

        # 注册到根 logger
        root_logger = logging.getLogger()
        root_logger.addHandler(self.handler)

        logger.info("LogCollector initialized with max_size=%d", max_size)

    def get_recent_logs(
        self, level: str = "WARNING", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """获取最近的日志。

        Args:
            level: 最低日志级别 ("ERROR", "WARNING", "INFO")
            limit: 最大返回条数

        Returns:
            日志列表
        """
        level_map = {"ERROR": logging.ERROR, "WARNING": logging.WARNING, "INFO": logging.INFO}
        min_level = level_map.get(level, logging.WARNING)

        filtered = [log for log in self.logs if log["level_num"] >= min_level]

        # 返回最新的 N 条（倒序）
        return list(reversed(filtered))[:limit]

    def clear(self) -> None:
        """清空日志队列。"""
        self.logs.clear()
        logger.info("LogCollector cleared")

    def shutdown(self) -> None:
        """关闭日志收集器，移除 handler。"""
        root_logger = logging.getLogger()
        root_logger.removeHandler(self.handler)
        logger.info("LogCollector shutdown")

