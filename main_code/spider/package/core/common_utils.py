"""
认证和错误处理的公共工具
提供装饰器和基础类，用于减少代码重复
"""

import logging
import functools
from typing import Callable, Any, Optional, Dict, List
# from ..auth.login import create_authenticated_session, LoginConfig  # 延迟导入以避免循环依赖
from ..auth.session_manager import session_manager
# from ..auth.error_manager import error_account_manager, ErrorType  # 延迟导入以避免循环依赖
from .logger_manager import setup_module_logger, setup_root_logger as _setup_root_logger


def authenticated_operation(error_accounts_list: Optional[List] = None):
    """
    认证操作装饰器，自动处理登录和登出逻辑
    
    Args:
        error_accounts_list: 用于记录错误账号的列表，如果为None则使用错误账号管理器
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # 获取用户名和密码
            username = getattr(self, 'username', None)
            password = getattr(self, 'password', None)
            
            if not username or not password:
                logging.error("用户名或密码未设置")
                return False
                
            # 创建认证会话
            # 延迟导入以避免循环依赖
            from ..auth.login import create_authenticated_session
            session = create_authenticated_session(username, password)
            if not session:
                logging.info(f"账号 {username} 登录失败")
                
                # 记录错误账号
                if error_accounts_list is not None:
                    error_accounts_list.append([username, password])
                else:
                    # 延迟导入以避免循环依赖
                    from ..auth.error_manager import error_account_manager, ErrorType
                    error_account_manager.add_error_account(
                        username, password, ErrorType.PASSWORD_ERROR, "登录失败"
                    )
                
                return False
            
            # 执行被装饰的函数
            try:
                result = func(self, *args, **kwargs)
                return result
            finally:
                # 确保退出登录
                session_manager.logout_session(username)
                logging.debug(f"账号 {username} 已退出登录")
                
        return wrapper
    return decorator


def session_required(func: Callable) -> Callable:
    """
    会话要求装饰器，确保函数执行时有有效的会话
    
    Args:
        func: 需要会话的函数
        
    Returns:
        装饰后的函数
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        # 获取用户名
        username = getattr(self, 'username', None)
        
        if not username:
            logging.error("用户名未设置")
            return None
            
        # 获取会话
        session = session_manager.get_session(username)
        if not session:
            logging.error(f"无法获取用户 {username} 的会话")
            return None
            
        # 执行被装饰的函数
        return func(self, *args, **kwargs)
        
    return wrapper


def setup_logger(name: str, log_file: str = None, config: dict = None) -> logging.Logger:
    """
    设置日志记录器

    Args:
        name: 日志记录器名称
        log_file: 日志文件路径
        config: 日志配置

    Returns:
        配置好的日志记录器
    """
    return setup_module_logger(name, log_file, config)


def setup_root_logger(log_file: str = None, config: dict = None) -> None:
    """
    设置根日志记录器，确保所有模块使用统一格式

    Args:
        log_file: 日志文件路径
        config: 日志配置
    """
    _setup_root_logger(log_file, config)


class BaseOperation:
    """
    基础操作类，封装通用的认证和错误处理功能
    """
    
    def __init__(self, username: str, password: str, logger_name: str = None):
        """
        初始化基础操作类
        
        Args:
            username: 用户名
            password: 密码
            logger_name: 日志记录器名称，如果为None则使用类名
        """
        self.username = username
        self.password = password
        self.logger_name = logger_name or self.__class__.__name__
        self.logger = logging.getLogger(self.logger_name)
        
    def login(self) -> bool:
        """
        执行登录操作
        
        Returns:
            登录成功返回True，失败返回False
        """
        # 创建认证会话
        # 延迟导入以避免循环依赖
        from ..auth.login import create_authenticated_session
        session = create_authenticated_session(self.username, self.password)
        if not session:
            self.logger.info(f"账号 {self.username} 登录失败")
            # 延迟导入以避免循环依赖
            from ..auth.error_manager import error_account_manager, ErrorType
            error_account_manager.add_error_account(
                self.username, self.password, ErrorType.PASSWORD_ERROR, "登录失败"
            )
            return False
            
        self.logger.info(f"账号 {self.username} 登录成功")
        return True
        
    def logout(self) -> None:
        """退出登录"""
        session_manager.logout_session(self.username)
        self.logger.debug(f"账号 {self.username} 已退出登录")
        
    def get_session(self):
        """
        获取当前用户的会话
        
        Returns:
            有效的会话对象，如果不存在则返回None
        """
        return session_manager.get_session(self.username)
        
    @authenticated_operation()
    def execute_with_auth(self, operation_func: Callable, *args, **kwargs) -> Any:
        """
        使用认证执行操作
        
        Args:
            operation_func: 需要认证的操作函数
            *args: 操作函数的位置参数
            **kwargs: 操作函数的关键字参数
            
        Returns:
            操作函数的返回值
        """
        # 这个方法会被装饰器自动处理登录和登出
        return operation_func(self, *args, **kwargs)


class AutoLoginBase(BaseOperation):
    """
    自动登录基类，继承自BaseOperation，提供更便捷的自动登录功能
    """
    
    def __init__(self, username: str, password: str, logger_name: str = None):
        super().__init__(username, password, logger_name)
        self._authenticated = False
        
    def __enter__(self):
        """上下文管理器入口，自动登录"""
        self._authenticated = self.login()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口，自动登出"""
        if self._authenticated:
            self.logout()
            self._authenticated = False
            
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return self._authenticated and self.get_session() is not None


def handle_request_errors(default_return=None, log_errors=True):
    """
    请求错误处理装饰器
    
    Args:
        default_return: 发生错误时的默认返回值
        log_errors: 是否记录错误日志
        
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    logging.error(f"执行 {func.__name__} 时出错: {str(e)}")
                return default_return
        return wrapper
    return decorator