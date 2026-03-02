"""统一日志模块"""

import logging
import sys
from pathlib import Path


def setup_logger(name: str = "rag_mcp", level: int = logging.INFO) -> logging.Logger:
    """
    创建并配置日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别
        
    Returns:
        配置好的日志记录器
    """
    logger = logging.getLogger(name)
    
    # 避免重复添加 handler
    if logger.handlers:
        return logger
    
    logger.setLevel(level)
    
    # 创建控制台处理器
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    
    # 设置日志格式
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger


# 全局日志实例
logger = setup_logger()
