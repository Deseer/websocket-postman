"""日志工具模块"""
import sys
from loguru import logger


def setup_logger(log_level: str = "INFO", log_file: str | None = None):
    """配置日志"""
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台输出
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )
    
    # 添加文件输出
    if log_file:
        logger.add(
            log_file,
            level=log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="7 days",
            compression="gz",
        )
    
    return logger


# 导出 logger 实例
__all__ = ["logger", "setup_logger"]
