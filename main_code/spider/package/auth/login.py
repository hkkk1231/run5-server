import requests
import logging
import time
from typing import Optional, Dict, List, Tuple, Union
from .error_manager import error_account_manager, ErrorType


class LoginConfig:
    """登录配置类，用于管理登录相关的配置参数"""
    
    def __init__(self, 
                 login_url: str = "https://lb.hnfnu.edu.cn/login",
                 timeout: int = 10,
                 max_retries: int = 3,
                 retry_delay: float = 2.0,
                 use_proxy: bool = False,
                 proxies: Optional[Dict[str, str]] = None,
                 custom_headers: Optional[Dict[str, str]] = None):
        """
        初始化登录配置
        
        Args:
            login_url: 登录接口URL
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试延迟时间（秒）
            use_proxy: 是否使用代理
            proxies: 代理配置
            custom_headers: 自定义请求头
        """
        self.login_url = login_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.use_proxy = use_proxy
        self.proxies = proxies or {}
        self.custom_headers = custom_headers or {}


def login(session: requests.Session, 
          username: str, 
          password: str, 
          config: Optional[LoginConfig] = None,
          track_errors: bool = True) -> Union[str, bool]:
    """
    执行登录操作，获取访问令牌
    
    Args:
        session: requests.Session对象，用于维持会话状态
        username: 用户名
        password: 密码
        config: 登录配置对象，如果为None则使用默认配置
        track_errors: 是否跟踪错误账号
        
    Returns:
        登录成功返回token字符串，失败返回False
    """
    # 使用默认配置如果没有提供配置
    if config is None:
        config = LoginConfig()
    
    # 准备登录数据
    data = {
        "username": username,
        "password": password,
        "code": "",
        "uuid": "",
    }
    
    # 准备请求头
    headers = {"Content-Type": "application/json"}
    if config.custom_headers:
        headers.update(config.custom_headers)
    
    # 记录登录尝试
    logging.info(f"正在尝试登录账号: {username}")
    
    # 执行登录请求，支持重试机制
    last_exception = None
    for attempt in range(config.max_retries):
        try:
            # 构建请求参数
            request_params = {
                "url": config.login_url,
                "json": data,
                "headers": headers,
                "timeout": config.timeout
            }
            
            # 添加代理配置（如果需要）
            if config.use_proxy and config.proxies:
                request_params["proxies"] = config.proxies
            
            # 发送登录请求
            login_response = session.post(**request_params)
            login_response.raise_for_status()  # 检查HTTP错误
            
            # 解析响应
            response_json = login_response.json()
            msg = response_json.get("msg")
            token = response_json.get("token")
            
            # 处理登录结果
            if msg != "操作成功":
                logging.warning(f"登录失败，原因: {msg}")
                
                # 如果是密码错误且需要跟踪错误账号
                if track_errors and msg == "用户不存在/密码错误":
                    error_account_manager.add_error_account(
                        username, password, ErrorType.PASSWORD_ERROR, msg
                    )
                    logging.info(f"密码错误，记录账号: {username}")
                # 其他错误也记录（如果需要跟踪）
                elif track_errors:
                    # 根据错误消息判断错误类型
                    if "网络" in msg or "连接" in msg or "超时" in msg:
                        error_type = ErrorType.NETWORK_ERROR
                    elif "系统" in msg or "服务器" in msg:
                        error_type = ErrorType.SYSTEM_ERROR
                    else:
                        error_type = ErrorType.UNKNOWN_ERROR
                    
                    error_account_manager.add_error_account(
                        username, password, error_type, msg
                    )
                    logging.debug(f"记录错误账号: {username}, 类型: {error_type.value}")
                
                return False
            else:
                # 登录成功
                logging.info("登录成功")
                
                # 检查token是否存在
                if not token:
                    logging.error("登录成功但未获取到token")
                    return False
                
                # 更新会话的Authorization头
                session.headers.update({
                    "Authorization": f"Bearer {token}"
                })
                logging.debug(f"Authorization头已更新: Bearer {token[:10]}...")

                return token

        except requests.exceptions.RequestException as e:
            last_exception = e
            # 控制台只显示简短信息
            logging.warning(f"登录请求异常 (尝试 {attempt + 1}/{config.max_retries})")
            # 详细异常信息只记录到文件
            logging.debug(f"异常详情: {str(e)}", exc_info=True)

            # 如果不是最后一次尝试，等待后重试
            if attempt < config.max_retries - 1:
                time.sleep(config.retry_delay)
        except ValueError as e:
            last_exception = e
            logging.error(f"响应解析异常")
            logging.debug(f"响应解析异常详情: {str(e)}")
            break  # JSON解析错误不需要重试

    # 所有尝试都失败了
    logging.error(f"登录失败，已达到最大重试次数: {config.max_retries}")

    # 记录错误账号（如果需要跟踪）
    if track_errors:
        error_account_manager.add_error_account(
            username, password, ErrorType.UNKNOWN_ERROR, f"登录失败: {last_exception}"
        )
    
    return False


def logout(session: requests.Session, config: Optional[LoginConfig] = None) -> bool:
    """
    退出登录，清理会话状态
    
    Args:
        session: requests.Session对象
        config: 登录配置对象，如果为None则使用默认配置
        
    Returns:
        退出成功返回True，失败返回False
    """
    # 使用默认配置如果没有提供配置
    if config is None:
        config = LoginConfig()
    
    logout_url = "https://lb.hnfnu.edu.cn/logout"
    
    # 准备退出登录的请求头
    logout_headers = {
        "custom-header": "{}", 
        "Content-Length": "0", 
        "Content-Type": "application/json"
    }
    
    try:
        # 发送退出登录请求
        response = session.post(
            url=logout_url,
            headers=logout_headers,
            timeout=config.timeout,
            proxies=config.proxies if config.use_proxy else None
        )
        response.raise_for_status()
        logging.info("已成功退出登录")
        return True
    except requests.exceptions.RequestException as e:
        logging.warning(f"退出登录请求失败: {str(e)}")
        return False
    finally:
        # 无论请求是否成功，都清理会话头
        keys_to_remove = ['custom-header', 'Authorization']
        for key in keys_to_remove:
            session.headers.pop(key, None)
        logging.debug("会话头已清理")


def get_error_accounts() -> Tuple[List[List[str]], List[List[str]]]:
    """
    获取所有错误账号列表
    
    Returns:
        Tuple[List[List[str]], List[List[str]]]: (error_accounts, password_error_accounts)
        第一个列表是所有错误账号，第二个列表是密码错误账号
    """
    # 从错误账号管理器获取所有错误账号
    all_errors = error_account_manager.get_all_error_accounts()
    
    # 获取密码错误账号
    password_errors = error_account_manager.get_error_accounts_by_type(ErrorType.PASSWORD_ERROR)
    
    # 转换为旧格式 [username, password]
    all_errors_list = [[err.username, err.password] for err in all_errors]
    password_errors_list = [[err.username, err.password] for err in password_errors]
    
    return all_errors_list, password_errors_list


def clear_error_accounts() -> None:
    """清空错误账号列表"""
    error_account_manager.clear_all_errors()
    logging.debug("错误账号列表已清空")


def create_authenticated_session(username: str, 
                                password: str, 
                                headers: Optional[Dict[str, str]] = None,
                                config: Optional[LoginConfig] = None,
                                track_errors: bool = True) -> Optional[requests.Session]:
    """
    创建并返回一个已认证的会话对象
    
    Args:
        username: 用户名
        password: 密码
        headers: 可选的初始请求头
        config: 登录配置对象，如果为None则使用默认配置
        track_errors: 是否跟踪错误账号
        
    Returns:
        登录成功返回认证的session对象，失败返回None
    """
    # 创建新会话
    session = requests.Session()
    
    # 添加初始请求头（如果提供）
    if headers:
        session.headers.update(headers)
    
    # 使用默认配置如果没有提供配置
    if config is None:
        config = LoginConfig()
    
    # 准备登录数据
    data = {
        "username": username,
        "password": password,
        "code": "",
        "uuid": "",
    }
    
    # 准备请求头
    request_headers = {"Content-Type": "application/json"}
    if config.custom_headers:
        request_headers.update(config.custom_headers)
    
    # 记录登录尝试
    logging.info(f"正在尝试登录账号: {username}")
    
    # 执行登录请求，支持重试机制
    last_exception = None
    for attempt in range(config.max_retries):
        try:
            # 构建请求参数
            request_params = {
                "url": config.login_url,
                "json": data,
                "headers": request_headers,
                "timeout": config.timeout
            }
            
            # 添加代理配置（如果需要）
            if config.use_proxy and config.proxies:
                request_params["proxies"] = config.proxies
            
            # 发送登录请求
            login_response = session.post(**request_params)
            login_response.raise_for_status()  # 检查HTTP错误
            
            # 解析响应
            response_json = login_response.json()
            msg = response_json.get("msg")
            token = response_json.get("token")
            
            # 处理登录结果
            if msg != "操作成功":
                logging.warning(f"登录失败，原因: {msg}")
                
                # 如果是密码错误且需要跟踪错误账号
                if track_errors and msg == "用户不存在/密码错误":
                    error_account_manager.add_error_account(
                        username, password, ErrorType.PASSWORD_ERROR, msg
                    )
                    logging.info(f"密码错误，记录账号: {username}")
                # 其他错误也记录（如果需要跟踪）
                elif track_errors:
                    # 根据错误消息判断错误类型
                    if "网络" in msg or "连接" in msg or "超时" in msg:
                        error_type = ErrorType.NETWORK_ERROR
                    elif "系统" in msg or "服务器" in msg:
                        error_type = ErrorType.SYSTEM_ERROR
                    else:
                        error_type = ErrorType.UNKNOWN_ERROR
                    
                    error_account_manager.add_error_account(
                        username, password, error_type, msg
                    )
                    logging.debug(f"记录错误账号: {username}, 类型: {error_type.value}")
                
                session.close()  # 关闭会话，释放资源
                return None
            else:
                # 登录成功
                logging.info("登录成功")
                
                # 检查token是否存在
                if not token:
                    logging.error("登录成功但未获取到token")
                    session.close()  # 关闭会话，释放资源
                    return None
                
                # 更新会话的Authorization头
                session.headers.update({
                    "Authorization": f"Bearer {token}"
                })
                logging.debug(f"Authorization头已更新: Bearer {token[:10]}...")

                return session

        except requests.exceptions.RequestException as e:
            last_exception = e
            # 控制台只显示简短信息
            logging.warning(f"登录请求异常 (尝试 {attempt + 1}/{config.max_retries})")
            # 详细异常信息只记录到文件
            logging.debug(f"异常详情: {str(e)}", exc_info=True)

            # 如果不是最后一次尝试，等待后重试
            if attempt < config.max_retries - 1:
                time.sleep(config.retry_delay)
        except ValueError as e:
            last_exception = e
            logging.error(f"响应解析异常")
            logging.debug(f"响应解析异常详情: {str(e)}")
            break  # JSON解析错误不需要重试

    # 所有尝试都失败了
    logging.error(f"登录失败，已达到最大重试次数: {config.max_retries}")

    # 记录错误账号（如果需要跟踪）
    if track_errors and [username, password] not in error_accounts:
        error_accounts.append([username, password])
    
    session.close()  # 关闭会话，释放资源
    return None


# 为了向后兼容，保留原始函数接口
def simple_login(session, username, password):
    """简化的登录函数，保持与原始login函数的兼容性"""
    return login(session, username, password)