# -*- coding: utf-8 -*-
"""
日志模块
"""

import logging
import os
from datetime import datetime


def setup_logger(log_path: str = None) -> logging.Logger:
    """
    配置日志记录器
    
    Args:
        log_path: 日志文件路径，默认为None（仅控制台输出）
        
    Returns:
        配置好的Logger实例
    """
    logger = logging.getLogger("trans_guide")
    logger.setLevel(logging.DEBUG)
    
    # 避免重复添加handler
    if logger.handlers:
        return logger
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)
    
    # 文件处理器
    if log_path:
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)
    
    return logger
