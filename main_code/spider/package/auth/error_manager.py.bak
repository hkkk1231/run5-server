"""
错误账号管理器
用于统一管理系统中的错误账号，区分不同类型的错误并提供持久化存储
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Set
from enum import Enum

# 使用统一的绝对路径配置
from paths import ERROR_ACCOUNTS_FILE, SPIDER_LOGS_DIR

# 导入日志管理器，创建专用日志器（避免使用根日志器导致重复打印）
from ..core.logger_manager import setup_logger
logger = setup_logger("error_manager", str(SPIDER_LOGS_DIR / "error_manager.log"))


class ErrorType(Enum):
    """错误类型枚举"""
    PASSWORD_ERROR = "password_error"  # 密码错误，永久跳过
    NETWORK_ERROR = "network_error"   # 网络错误，可重试
    SYSTEM_ERROR = "system_error"     # 系统错误，可重试
    UNKNOWN_ERROR = "unknown_error"   # 未知错误，可重试


class ErrorAccount:
    """错误账号信息类"""
    
    def __init__(self, username: str, password: str, error_type: ErrorType, 
                 error_message: str = "", first_occurrence: float = None,
                 last_occurrence: float = None, retry_count: int = 0):
        self.username = username
        self.password = password
        self.error_type = error_type
        self.error_message = error_message
        self.first_occurrence = first_occurrence or time.time()
        self.last_occurrence = last_occurrence or time.time()
        self.retry_count = retry_count
    
    def to_dict(self) -> Dict:
        """转换为字典格式"""
        return {
            "username": self.username,
            "password": self.password,
            "error_type": self.error_type.value,
            "error_message": self.error_message,
            "first_occurrence": self.first_occurrence,
            "last_occurrence": self.last_occurrence,
            "retry_count": self.retry_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ErrorAccount':
        """从字典创建对象"""
        return cls(
            username=data["username"],
            password=data["password"],
            error_type=ErrorType(data["error_type"]),
            error_message=data.get("error_message", ""),
            first_occurrence=data.get("first_occurrence", time.time()),
            last_occurrence=data.get("last_occurrence", time.time()),
            retry_count=data.get("retry_count", 0)
        )
    
    def update_occurrence(self, error_message: str = ""):
        """更新错误发生时间"""
        self.last_occurrence = time.time()
        self.retry_count += 1
        if error_message:
            self.error_message = error_message


class ErrorAccountManager:
    """错误账号管理器"""
    
    def __init__(self, storage_path: str = None):
        """
        初始化错误账号管理器

        Args:
            storage_path: 错误账号存储文件路径，如果为None则使用默认路径
        """
        if storage_path is None:
            storage_path = ERROR_ACCOUNTS_FILE

        self.storage_path = storage_path
        self.error_accounts: Dict[str, ErrorAccount] = {}  # 键为username

        # 确保存储目录存在
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)

        # 加载已有的错误账号
        self.load_error_accounts()
    
    def add_error_account(self, username: str, password: str, error_type: ErrorType, 
                         error_message: str = "") -> bool:
        """
        添加或更新错误账号
        
        Args:
            username: 用户名
            password: 密码
            error_type: 错误类型
            error_message: 错误信息
            
        Returns:
            是否是新增的错误账号
        """
        is_new = username not in self.error_accounts
        
        if is_new:
            self.error_accounts[username] = ErrorAccount(
                username, password, error_type, error_message
            )
            logger.info(f"新增错误账号: {username}, 类型: {error_type.value}")
        else:
            self.error_accounts[username].update_occurrence(error_message)
            logger.debug(f"更新错误账号: {username}, 重试次数: {self.error_accounts[username].retry_count}")
        
        # 保存到文件
        self.save_error_accounts()
        return is_new
    
    def remove_error_account(self, username: str) -> bool:
        """
        移除错误账号
        
        Args:
            username: 用户名
            
        Returns:
            是否成功移除
        """
        if username in self.error_accounts:
            del self.error_accounts[username]
            self.save_error_accounts()
            logger.info(f"移除错误账号: {username}")
            return True
        return False
    
    def get_error_account(self, username: str) -> Optional[ErrorAccount]:
        """
        获取错误账号信息
        
        Args:
            username: 用户名
            
        Returns:
            错误账号信息，如果不存在则返回None
        """
        return self.error_accounts.get(username)
    
    def get_error_accounts_by_type(self, error_type: ErrorType) -> List[ErrorAccount]:
        """
        根据错误类型获取错误账号列表
        
        Args:
            error_type: 错误类型
            
        Returns:
            错误账号列表
        """
        return [account for account in self.error_accounts.values() 
                if account.error_type == error_type]
    
    def get_all_error_accounts(self) -> Dict[str, ErrorAccount]:
        """获取所有错误账号"""
        return self.error_accounts.copy()
    
    def is_password_error(self, username: str) -> bool:
        """
        检查账号是否是密码错误
        
        Args:
            username: 用户名
            
        Returns:
            是否是密码错误
        """
        account = self.error_accounts.get(username)
        return account is not None and account.error_type == ErrorType.PASSWORD_ERROR
    
    def is_retryable_error(self, username: str) -> bool:
        """
        检查账号是否是可重试错误
        
        Args:
            username: 用户名
            
        Returns:
            是否是可重试错误
        """
        account = self.error_accounts.get(username)
        if account is None:
            return True  # 没有错误记录，可以重试
        
        # 密码错误不可重试，其他类型可重试
        return account.error_type != ErrorType.PASSWORD_ERROR
    
    def clear_all_errors(self):
        """清空所有错误账号"""
        self.error_accounts.clear()
        self.save_error_accounts()
        logger.info("已清空所有错误账号")
    
    def clear_errors_by_type(self, error_type: ErrorType):
        """
        清空指定类型的错误账号
        
        Args:
            error_type: 错误类型
        """
        usernames_to_remove = [
            username for username, account in self.error_accounts.items()
            if account.error_type == error_type
        ]
        
        for username in usernames_to_remove:
            del self.error_accounts[username]
        
        if usernames_to_remove:
            self.save_error_accounts()
            logger.info(f"已清空 {len(usernames_to_remove)} 个 {error_type.value} 类型的错误账号")
    
    def save_error_accounts(self):
        """保存错误账号到文件"""
        try:
            data = {
                "last_updated": time.time(),
                "error_accounts": {
                    username: account.to_dict()
                    for username, account in self.error_accounts.items()
                }
            }
            
            with open(self.storage_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            logger.error(f"保存错误账号到文件失败: {e}")
    
    def load_error_accounts(self):
        """从文件加载错误账号"""
        if not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            error_accounts_data = data.get("error_accounts", {})
            for username, account_data in error_accounts_data.items():
                self.error_accounts[username] = ErrorAccount.from_dict(account_data)
            
            logger.info(f"从文件加载了 {len(self.error_accounts)} 个错误账号")

        except Exception as e:
            logger.error(f"从文件加载错误账号失败: {e}")
    
    def get_error_summary(self) -> Dict[str, int]:
        """
        获取错误账号统计摘要
        
        Returns:
            各类型错误账号的数量统计
        """
        summary = {
            "total": len(self.error_accounts),
            "password_error": 0,
            "network_error": 0,
            "system_error": 0,
            "unknown_error": 0
        }
        
        for account in self.error_accounts.values():
            summary[account.error_type.value] += 1
        
        return summary
    
    def cleanup_old_errors(self, days: int = 7):
        """
        清理超过指定天数的可重试错误账号
        
        Args:
            days: 天数阈值
        """
        current_time = time.time()
        usernames_to_remove = []
        
        for username, account in self.error_accounts.items():
            # 只清理可重试的错误类型
            if (account.error_type != ErrorType.PASSWORD_ERROR and 
                current_time - account.last_occurrence > days * 24 * 60 * 60):
                usernames_to_remove.append(username)
        
        for username in usernames_to_remove:
            del self.error_accounts[username]
        
        if usernames_to_remove:
            self.save_error_accounts()
            logger.info(f"清理了 {len(usernames_to_remove)} 个超过 {days} 天的可重试错误账号")


# 创建全局错误账号管理器实例
error_account_manager = ErrorAccountManager()


# 为了向后兼容，保留一些旧接口
def get_error_accounts() -> Tuple[List[List[str]], List[List[str]]]:
    """
    获取错误账号列表（向后兼容接口）
    
    Returns:
        返回一个元组，包含两个列表：
        - 第一个列表是一般错误账号
        - 第二个列表是密码错误账号
    """
    all_accounts = error_account_manager.get_all_error_accounts()
    
    general_errors = []
    password_errors = []
    
    for account in all_accounts.values():
        account_info = [account.username, account.password]
        if account.error_type == ErrorType.PASSWORD_ERROR:
            password_errors.append(account_info)
        else:
            general_errors.append(account_info)
    
    return general_errors, password_errors


def clear_error_accounts():
    """清空错误账号列表（向后兼容接口）"""
    error_account_manager.clear_all_errors()