"""
通用错误处理基础类
提供统一的错误处理、重试机制和日志记录功能
"""
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
from enum import Enum
# from ..auth.error_manager import error_account_manager, ErrorType  # 延迟导入以避免循环依赖
from .logger_manager import get_logger


class RetryStrategy(Enum):
    """重试策略枚举"""
    FIXED_INTERVAL = "fixed_interval"  # 固定间隔重试
    EXPONENTIAL_BACKOFF = "exponential_backoff"  # 指数退避重试
    LINEAR_BACKOFF = "linear_backoff"  # 线性退避重试


class ErrorSeverity(Enum):
    """错误严重程度枚举"""
    LOW = "low"  # 低级错误，不影响主要功能
    MEDIUM = "medium"  # 中级错误，影响部分功能
    HIGH = "high"  # 高级错误，影响主要功能
    CRITICAL = "critical"  # 严重错误，导致系统崩溃


class ErrorHandler:
    """错误处理器基类"""
    
    def __init__(self, name: Optional[str] = None):
        """
        初始化错误处理器
        
        Args:
            name: 错误处理器名称，如果为None则使用类名
        """
        self.logger = get_logger(name or self.__class__.__name__)
        self.error_counts: Dict[str, int] = {}
        self.error_handlers: Dict[Type[Exception], Callable] = {}
        
    def register_handler(self, exception_type: Type[Exception], handler: Callable):
        """
        注册特定异常类型的处理函数
        
        Args:
            exception_type: 异常类型
            handler: 处理函数，接收异常对象作为参数
        """
        self.error_handlers[exception_type] = handler
        
    def handle_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        处理错误
        
        Args:
            error: 异常对象
            context: 错误上下文信息
            
        Returns:
            bool: 是否已处理错误
        """
        error_type = type(error).__name__
        self.error_counts[error_type] = self.error_counts.get(error_type, 0) + 1
        
        # 记录错误
        self.logger.error(f"发生错误: {error_type}: {str(error)}", exc_info=True)
        if context:
            self.logger.error(f"错误上下文: {context}")
            
        # 查找并执行注册的错误处理函数
        for exc_type, handler in self.error_handlers.items():
            if isinstance(error, exc_type):
                try:
                    handler(error, context)
                    return True
                except Exception as handler_error:
                    self.logger.error(f"错误处理函数执行失败: {handler_error}")
                    
        return False
        
    def get_error_stats(self) -> Dict[str, int]:
        """获取错误统计信息"""
        return self.error_counts.copy()
        
    def reset_error_stats(self):
        """重置错误统计"""
        self.error_counts.clear()


def retry_on_exception(
    max_retries: int = 3,
    retry_strategy: RetryStrategy = RetryStrategy.FIXED_INTERVAL,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0,
    exceptions: Union[Type[Exception], tuple] = Exception,
    on_retry: Optional[Callable[[Exception, int], None]] = None,
    logger_name: Optional[str] = None
):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        retry_strategy: 重试策略
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        backoff_multiplier: 退避倍数（用于指数退避和线性退避）
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数，接收异常和当前重试次数
        logger_name: 日志记录器名称
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            _logger = get_logger(logger_name or func.__module__)
            last_exception = None
            
            for attempt in range(max_retries + 1):  # 包括初始尝试
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        _logger.error(f"函数 {func.__name__} 在 {max_retries} 次重试后仍然失败: {str(e)}")
                        raise
                        
                    # 计算延迟时间
                    if retry_strategy == RetryStrategy.FIXED_INTERVAL:
                        delay = base_delay
                    elif retry_strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
                        delay = min(base_delay * (backoff_multiplier ** attempt), max_delay)
                    elif retry_strategy == RetryStrategy.LINEAR_BACKOFF:
                        delay = min(base_delay * (1 + backoff_multiplier * attempt), max_delay)
                    else:
                        delay = base_delay
                        
                    _logger.warning(f"函数 {func.__name__} 执行失败 (尝试 {attempt + 1}/{max_retries + 1}): {str(e)}, {delay}秒后重试")
                    
                    # 执行重试回调
                    if on_retry:
                        try:
                            on_retry(e, attempt + 1)
                        except Exception as callback_error:
                            _logger.error(f"重试回调函数执行失败: {callback_error}")
                            
                    time.sleep(delay)
                    
            # 这行代码理论上不会执行，但为了类型检查
            raise last_exception
            
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    default_return: Any = None,
    exceptions: Union[Type[Exception], tuple] = Exception,
    log_errors: bool = True,
    logger_name: Optional[str] = None,
    error_handler: Optional[ErrorHandler] = None,
    context: Optional[Dict[str, Any]] = None
) -> Any:
    """
    安全执行函数，捕获异常并返回默认值
    
    Args:
        func: 要执行的函数
        default_return: 发生异常时的默认返回值
        exceptions: 要捕获的异常类型
        log_errors: 是否记录错误
        logger_name: 日志记录器名称
        error_handler: 错误处理器
        context: 错误上下文信息
        
    Returns:
        函数执行结果或默认返回值
    """
    _logger = get_logger(logger_name or func.__module__)
    
    try:
        return func()
    except exceptions as e:
        if log_errors:
            _logger.error(f"安全执行函数 {func.__name__} 时发生错误: {str(e)}", exc_info=True)
            if context:
                _logger.error(f"错误上下文: {context}")
                
        if error_handler:
            error_handler.handle_error(e, context)
            
        return default_return


class NetworkErrorHandler(ErrorHandler):
    """网络错误处理器"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        # 注册常见网络错误的处理函数
        self.register_handler(ConnectionError, self._handle_connection_error)
        self.register_handler(TimeoutError, self._handle_timeout_error)
        
    def _handle_connection_error(self, error: ConnectionError, context: Optional[Dict[str, Any]]):
        """处理连接错误"""
        self.logger.warning(f"网络连接错误: {str(error)}")
        # 可以在这里添加重连逻辑
        
    def _handle_timeout_error(self, error: TimeoutError, context: Optional[Dict[str, Any]]):
        """处理超时错误"""
        self.logger.warning(f"网络请求超时: {str(error)}")
        # 可以在这里添加重试逻辑


class AuthenticationErrorHandler(ErrorHandler):
    """认证错误处理器"""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        # 注册认证错误的处理函数
        self.register_handler(ValueError, self._handle_auth_error)
        
    def _handle_auth_error(self, error: ValueError, context: Optional[Dict[str, Any]]):
        """处理认证错误"""
        error_msg = str(error).lower()
        if "登录" in error_msg or "认证" in error_msg or "token" in error_msg:
            self.logger.error(f"认证失败: {str(error)}")
            
            # 如果上下文中有账号信息，将其添加到错误账号管理器
            if context and "username" in context:
                username = context["username"]
                # 延迟导入以避免循环依赖
                from ..auth.error_manager import error_account_manager, ErrorType
                error_account_manager.add_error_account(username, ErrorType.PASSWORD_ERROR, str(error))
                self.logger.info(f"已将账号 {username} 添加到错误账号列表")


# 创建默认的错误处理器实例
network_error_handler = NetworkErrorHandler()
auth_error_handler = AuthenticationErrorHandler()