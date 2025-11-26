"""
统一日志管理模块
提供统一的日志配置、格式化、轮转和归档功能
"""

import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# 使用统一的绝对路径配置
from paths import SPIDER_LOGS_DIR


class LoggerManager:
    """日志管理器，提供统一的日志配置和管理"""
    
    # 日志级别映射
    LOG_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    # 默认日志配置
    DEFAULT_CONFIG = {
        'level': 'DEBUG',  # Logger 本身设为 DEBUG 接收所有消息
        'file_format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # 文件详细格式
        'console_format': '%(asctime)s- %(message)s',  # 控制台简洁格式
        'file_date_format': '%Y-%m-%d %H:%M:%S',  # 文件日期格式
        'console_date_format': '%H:%M',  # 控制台时间格式
        'backup_count': 7,  # 保留7天的日志
        'max_bytes': 10 * 1024 * 1024,  # 10MB
        'console_output': True
    }
    
    # 已创建的日志器缓存
    _loggers: Dict[str, logging.Logger] = {}
    
    @classmethod
    def setup_logger(cls, 
                    name: str, 
                    log_file: Optional[str] = None,
                    config: Optional[Dict[str, Any]] = None,
                    force_recreate: bool = False) -> logging.Logger:
        """
        设置并返回一个配置好的日志器
        
        Args:
            name: 日志器名称
            log_file: 日志文件路径，如果为None则只输出到控制台
            config: 自定义配置，会与默认配置合并
            force_recreate: 是否强制重新创建日志器
            
        Returns:
            配置好的日志器
        """
        # 如果日志器已存在且不强制重新创建，直接返回
        if not force_recreate and name in cls._loggers:
            return cls._loggers[name]
        
        # 合并配置
        final_config = cls.DEFAULT_CONFIG.copy()
        if config:
            final_config.update(config)
        
        # 创建日志器
        logger = logging.getLogger(name)
        logger.setLevel(cls.LOG_LEVELS.get(final_config['level'].upper(), logging.INFO))

        # 清除已有的处理器
        logger.handlers.clear()

        # 防止日志传播到根日志器，避免重复打印
        logger.propagate = False

        # 设置控制台格式器（简洁）
        console_formatter = logging.Formatter(
            fmt=final_config['console_format'],
            datefmt=final_config['console_date_format']
        )

        # 设置文件格式器（详细）
        file_formatter = logging.Formatter(
            fmt=final_config['file_format'],
            datefmt=final_config['file_date_format']
        )

        # 添加控制台处理器
        if final_config.get('console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(logging.INFO)  # 控制台只显示 INFO 及以上级别
            logger.addHandler(console_handler)

        # 添加文件处理器
        if log_file:
            # 确保日志目录存在
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用轮转文件处理器
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=final_config['max_bytes'],
                backupCount=final_config['backup_count'],
                encoding='utf-8'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别（包括 DEBUG）
            logger.addHandler(file_handler)
        
        # 缓存日志器
        cls._loggers[name] = logger
        return logger

    @classmethod
    def setup_root_logger(cls,
                         log_file: Optional[str] = None,
                         config: Optional[Dict[str, Any]] = None) -> None:
        """
        配置根日志器，确保所有模块的日志格式统一

        Args:
            log_file: 日志文件路径
            config: 自定义配置
        """
        # 合并配置
        final_config = cls.DEFAULT_CONFIG.copy()
        if config:
            final_config.update(config)

        # 获取根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(cls.LOG_LEVELS.get(final_config['level'].upper(), logging.INFO))

        # 清除已有的处理器
        root_logger.handlers.clear()

        # 设置控制台格式器（简洁）
        console_formatter = logging.Formatter(
            fmt=final_config['console_format'],
            datefmt=final_config['console_date_format']
        )

        # 设置文件格式器（详细）
        file_formatter = logging.Formatter(
            fmt=final_config['file_format'],
            datefmt=final_config['file_date_format']
        )

        # 添加控制台处理器
        if final_config.get('console_output', True):
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(console_formatter)
            console_handler.setLevel(logging.INFO)  # 控制台只显示 INFO 及以上级别
            root_logger.addHandler(console_handler)

        # 添加文件处理器
        if log_file:
            # 确保日志目录存在
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            # 使用轮转文件处理器
            file_handler = logging.handlers.RotatingFileHandler(
                filename=log_file,
                maxBytes=final_config['max_bytes'],
                backupCount=final_config['backup_count'],
                encoding='utf-8'
            )
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别（包括 DEBUG）
            root_logger.addHandler(file_handler)
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取已创建的日志器
        
        Args:
            name: 日志器名称
            
        Returns:
            日志器实例，如果不存在则返回根日志器
        """
        return cls._loggers.get(name, logging.getLogger())
    
    @classmethod
    def setup_module_logger(cls, 
                           module_name: str, 
                           log_file: Optional[str] = None,
                           config: Optional[Dict[str, Any]] = None) -> logging.Logger:
        """
        为模块设置日志器，自动处理日志文件路径
        
        Args:
            module_name: 模块名称
            log_file: 日志文件路径，如果为None则使用默认路径
            config: 自定义配置
            
        Returns:
            配置好的日志器
        """
        # 如果没有指定日志文件，使用默认路径
        if log_file is None:
            log_file = str(SPIDER_LOGS_DIR / f"{module_name}.log")
        
        return cls.setup_logger(module_name, log_file, config)
    
    @classmethod
    def archive_old_logs(cls, log_dir: str, days_to_keep: int = 30) -> None:
        """
        归档旧日志文件
        
        Args:
            log_dir: 日志目录
            days_to_keep: 保留天数，超过此天数的日志将被归档
        """
        log_path = Path(log_dir)
        if not log_path.exists():
            return
        
        # 创建归档目录
        archive_dir = log_path / "archive"
        archive_dir.mkdir(exist_ok=True)
        
        # 获取当前时间
        now = datetime.now()
        
        # 遍历日志文件
        for log_file in log_path.glob("*.log*"):
            # 获取文件修改时间
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            # 如果文件超过保留天数，移动到归档目录
            if (now - file_time).days > days_to_keep:
                archive_file = archive_dir / log_file.name
                log_file.rename(archive_file)
                print(f"已归档日志文件: {log_file} -> {archive_file}")
    
    @classmethod
    def cleanup_old_logs(cls, log_dir: str, days_to_keep: int = 90) -> None:
        """
        清理旧的归档日志文件
        
        Args:
            log_dir: 日志目录
            days_to_keep: 保留天数，超过此天数的归档日志将被删除
        """
        log_path = Path(log_dir)
        archive_dir = log_path / "archive"
        
        if not archive_dir.exists():
            return
        
        # 获取当前时间
        now = datetime.now()
        
        # 遍历归档日志文件
        for log_file in archive_dir.glob("*.log*"):
            # 获取文件修改时间
            file_time = datetime.fromtimestamp(log_file.stat().st_mtime)
            
            # 如果文件超过保留天数，删除
            if (now - file_time).days > days_to_keep:
                log_file.unlink()
                print(f"已删除旧日志文件: {log_file}")


# 便捷函数
def setup_logger(name: str, 
                log_file: Optional[str] = None,
                config: Optional[Dict[str, Any]] = None,
                force_recreate: bool = False) -> logging.Logger:
    """便捷函数：设置日志器"""
    return LoggerManager.setup_logger(name, log_file, config, force_recreate)


def get_logger(name: str) -> logging.Logger:
    """便捷函数：获取日志器"""
    return LoggerManager.get_logger(name)


def setup_module_logger(module_name: str, 
                       log_file: Optional[str] = None,
                       config: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """便捷函数：为模块设置日志器"""
    return LoggerManager.setup_module_logger(module_name, log_file, config)


def archive_old_logs(log_dir: str, days_to_keep: int = 30) -> None:
    """便捷函数：归档旧日志"""
    LoggerManager.archive_old_logs(log_dir, days_to_keep)


def cleanup_old_logs(log_dir: str, days_to_keep: int = 90) -> None:
    """便捷函数：清理旧日志"""
    LoggerManager.cleanup_old_logs(log_dir, days_to_keep)


def setup_root_logger(log_file: Optional[str] = None,
                     config: Optional[Dict[str, Any]] = None) -> None:
    """便捷函数：配置根日志器"""
    LoggerManager.setup_root_logger(log_file, config)