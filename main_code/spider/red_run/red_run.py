import os
import sys
import time
import requests
import random
import queue
import argparse
import json
from concurrent.futures import ThreadPoolExecutor

# 统一使用绝对导入，基于项目根目录的现代pathlib方式
# 项目根目录：run5-server
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 统一导入：所有模块都使用绝对导入
from main_code.spider.package.network.get_headers import get_headers
from main_code.spider.package.network.get_ip_port import get_ip_port
from main_code.spider.package.data import filter
from main_code.spider.package.auth.login import create_authenticated_session, LoginConfig
from main_code.spider.package.auth.session_manager import session_manager
from main_code.spider.package.core.common_utils import setup_logger, authenticated_operation
from main_code.spider.package.core.error_handler import safe_execute, auth_error_handler

# 统一的路径配置
from paths import SPIDER_LOGS_DIR

# 配置日志器：控制台只显示INFO及以上级别，文件记录所有级别
logger_config = {
    'level': 'DEBUG',  # 日志器级别设为DEBUG，接收所有消息
    'console_output': True,  # 允许控制台输出
    'console_format': '%(asctime)s - %(levelname)s - %(message)s',  # 控制台简洁格式
    'file_format': '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'  # 文件详细格式
}

logger = setup_logger("redrun", str(SPIDER_LOGS_DIR / "redrun_log.txt"), config=logger_config)

def login_wrapper(username, inner_password):
    # 配置登录参数，不使用代理
    login_config = LoginConfig(
        timeout=5,
        max_retries=3,
        retry_delay=2,
        use_proxy=False,  # 不使用代理
        proxies=None  # 不设置代理
    )
    
    # 使用统一的会话管理器创建认证会话
    headers = get_headers()
    session = create_authenticated_session(username, inner_password, headers=headers, config=login_config)
    
    if not session:
        logger.info(f"{username}的密码错误")
        return None
    
    # 将会话存储到会话管理器中
    session_manager._active_sessions[username] = session
    session_manager._session_tokens[username] = session.headers.get("Authorization", "").replace("Bearer ", "")
    session_manager._session_last_used[username] = time.time()
    
    return session_manager._session_tokens[username]


@authenticated_operation
def sign_up(account):
    # 请求报名页面url
    sign_url = "https://lb.hnfnu.edu.cn/school/competition"
    data = {"competitionId": 37, "competitionName": "环校跑"}
    
    # 从会话管理器获取会话
    session = session_manager.get_session(account)
    if not session:
        logger.error(f"无法获取账号 {account} 的会话")
        return False
    
    try:
        # 提交报名数据
        logger.debug(f"账号 {account} 开始报名环校跑")
        sign_response = session.post(json=data, url=sign_url, headers=session.headers)
        sign_response.raise_for_status()  # 检查HTTP错误
        
        # 解析报名响应
        response_json = sign_response.json()
        msg = response_json.get("msg", "")
        
        # 检查报名结果
        if msg == "操作成功" or "报名成功" in msg:
            logger.info(f"账号 {account} 环校跑报名成功")
            return True
        elif "已参加该竞赛" in msg or "已报名" in msg:
            logger.info(f"账号 {account} 已经报名过环校跑")
            return True
        else:
            logger.warning(f"账号 {account} 环校跑报名失败: {msg}")
            logger.debug(f"账号 {account} 报名响应详情: {response_json}")
            return False
            
    except Exception as e:
        logger.error(f"账号 {account} 报名请求异常: {str(e)}")
        logger.debug(f"账号 {account} 报名异常详情", exc_info=True)
        return False

@authenticated_operation
def start(account):
    """
    开始跑步流程
    
    该函数执行以下步骤：
    1. 获取用户会话
    2. 确保用户已报名
    3. 请求跑步页面获取必要数据
    4. 提交开始跑步的请求
    5. 提取并返回challenge_id用于后续结束跑步
    
    Args:
        account (str): 用户账号
        
    Returns:
        str/int: challenge_id 如果成功，否则返回None
    """
    # 从会话管理器获取会话
    session = session_manager.get_session(account)
    if not session:
        logger.error(f"无法获取账号 {account} 的会话")
        return None
    
    # 报名
    if not sign_up(account):
        logger.error(f"账号 {account} 报名失败")
        return None
    
    # 开始跑步url（使用正确的URL）
    start_url = "https://lb.hnfnu.edu.cn/school/challenges"
    logger.debug(f"账号 {account} 开始跑步请求: {start_url}")
    
    try:
        # 使用空数据对象开始跑步（参考旧版本成功实现）
        data = {}
        logger.debug(f"账号 {account} 提交开始跑步请求")
        
        # 提交开始跑步的请求
        start_response = session.post(json=data, url=start_url, headers=session.headers)
        start_response.raise_for_status()
        
        # 从响应中提取challenge_id（参考旧版本实现）
        try:
            response_json = start_response.json()
            msg = response_json.get("msg", "")
            
            # 检查是否已经完成
            if msg == "今日已完成挑战,请明天再来":
                logger.info(f"账号 {account} 今天跑过了")
                return None
            
            # 提取challenge_id
            response_data = response_json.get("data", {})
            if isinstance(response_data, dict) and "challengeId" in response_data:
                challenge_id = response_data["challengeId"]
                logger.info(f"账号 {account} 开始跑步成功，challenge_id: {challenge_id}")
                return challenge_id
            else:
                logger.error(f"账号 {account} 响应中未找到challenge_id")
                logger.debug(f"账号 {account} 响应数据: {response_json}")
                return None
                
        except (ValueError, KeyError) as e:
            logger.error(f"账号 {account} 解析开始跑步响应失败: {str(e)}")
            logger.debug(f"账号 {account} 原始响应内容: {start_response.text[:200]}...")
            return None
        
    except Exception as e:
        logger.error(f"账号 {account} 开始跑步时发生错误: {str(e)}")
        return None


def wait_time(account, mintime=1551, maxtime=1682):
    """
    等待跑步时间
    
    该函数会在指定的时间范围内随机等待，并定期记录剩余时间
    
    Args:
        account (str): 用户账号
        mintime (int): 最小等待时间（秒）
        maxtime (int): 最大等待时间（秒）
    """
    seconds = random.randint(mintime, maxtime)
    logger.debug(f"账号 {account} 开始等待跑步时间，随机等待 {seconds} 秒")
    
    start_time = time.time()
    while True:
        elapsed_time = time.time() - start_time
        remaining = seconds - int(elapsed_time)
        if remaining <= 0:
            logger.debug(f"账号 {account} 等待时间结束")
            break
            
        # 每分钟记录一次剩余时间
        if int(elapsed_time) % 60 == 0:
            mins, secs = divmod(remaining, 60)
            # 使用INFO级别记录，这样会同时显示在控制台和日志中
            timer = f"{account} 还需：{mins:02d}min"
            logger.info(timer)
            # 使用DEBUG级别记录更详细的信息，只记录在日志文件中
            logger.debug(f"账号 {account} 已等待 {int(elapsed_time)} 秒，剩余 {mins:02d}:{secs:02d}")
            
        time.sleep(1)


@authenticated_operation
def finish(challenge_id, account):
    """
    结束跑步流程
    
    该函数执行以下步骤：
    1. 验证参数有效性
    2. 获取用户会话
    3. 构造结束跑步的请求URL
    4. 发送PUT请求结束跑步
    5. 解析响应结果
    6. 根据结果记录完成状态
    
    Args:
        challenge_id (str/int): 跑步挑战ID，用于标识具体的跑步记录
        account (str): 用户账号
        
    Returns:
        bool: 如果成功结束跑步返回True，否则返回False
    """
    # 参数验证
    if not challenge_id:
        logger.error(f"账号 {account} 结束跑步失败: challenge_id为空")
        return False
    
    if not account:
        logger.error("结束跑步失败: 账号为空")
        return False
    
    logger.debug(f"账号 {account} 准备结束跑步，challenge_id: {challenge_id}")
    
    # 从会话管理器获取会话
    session = session_manager.get_session(account)
    if not session:
        logger.error(f"无法获取账号 {account} 的会话，可能需要重新登录")
        return False
    
    # 构造结束跑步的URL
    finish_url = f"https://lb.hnfnu.edu.cn/school/challenges?challengeId={challenge_id}"
    logger.debug(f"账号 {account} 结束跑步URL: {finish_url}")
    
    # 提交结束跑步请求
    try:
        logger.debug(f"账号 {account} 发送结束跑步请求")
        start_response = session.put(url=finish_url, headers=session.headers)
        
        # 检查HTTP状态码
        if start_response.status_code != 200:
            logger.error(f"账号 {account} 结束跑步请求失败，状态码: {start_response.status_code}")
            return False
        
        # 解析响应JSON
        try:
            response_data = start_response.json()
            logger.debug(f"账号 {account} 结束跑步响应数据: {response_data}")
        except ValueError as e:
            logger.error(f"账号 {account} 解析结束跑步响应失败: {str(e)}")
            # 尝试获取原始响应文本
            logger.debug(f"账号 {account} 原始响应内容: {start_response.text[:200]}...")
            return False
        
        # 提取结果消息
        result_msg = response_data.get('msg', '')
        if not result_msg:
            # 尝试其他可能的消息字段
            result_msg = response_data.get('message', '') or response_data.get('result', '')
        
        logger.info(f"账号 {account} 结束跑步结果: {result_msg}")
        
        # 判断是否成功结束
        success_indicators = ["操作成功", "成功", "success", "completed", "完成"]
        is_success = any(indicator in result_msg.lower() for indicator in [s.lower() for s in success_indicators])
        
        if is_success:
            # 成功结束，记录到完成配置
            try:
                filter.add_one(account)
                logger.info(f"账号 {account} 红色跑完成，已记录到完成列表")
            except Exception as e:
                logger.error(f"账号 {account} 记录完成状态失败: {str(e)}")
                # 即使记录失败，也认为跑步成功
        else:
            # 结束失败，记录详细信息
            logger.warning(f"账号 {account} 结束跑步失败，不记录完成状态")
            logger.debug(f"账号 {account} 失败详情: {response_data}")
            
            # 检查是否是特定的错误类型
            if "未开始" in result_msg or "not started" in result_msg.lower():
                logger.warning(f"账号 {account} 可能还没有开始跑步")
            elif "已结束" in result_msg or "already" in result_msg.lower():
                logger.warning(f"账号 {account} 跑步可能已经结束了")
        
        return is_success
        
    except Exception as e:
        logger.error(f"账号 {account} 结束跑步请求异常: {str(e)}", exc_info=True)
        return False

def logout_wrapper(account):
    # 使用会话管理器退出登录
    session_manager.logout_session(account)

def main(q, case="报名加跑步", accounts=None):
    """处理红色跑任务的主函数
    
    Args:
        q: 队列对象，用于存储账号密码
        case: 处理类型，默认为"报名加跑步"
        accounts: 账号密码列表，如果为None则从表格中获取需要红色跑的用户
    """
    # 如果没有提供账号列表，则使用过滤函数获取需要红色跑的用户
    if accounts is None:
        accounts = safe_execute(
            lambda: filter.get_red_run_users(),
            default_return=[],
            logger_name="redrun",
            context={"operation": "get_red_run_users"}
        )
        logger.info(f"从表格获取到需要红色跑的用户数量: {len(accounts)}")
    
    # 将账号密码放入队列
    for account_password in accounts:
        q.put(account_password)
    
    while not q.empty():
        try:
            account, password = q.get_nowait()
            # 使用安全执行函数处理每个账号
            safe_execute(
                lambda: process_single_account(account, password, case),
                logger_name="redrun",
                error_handler=auth_error_handler,
                context={"username": account, "operation": "process_red_run_account"}
            )
        except queue.Empty:
            break


def process_single_account(account, password, case):
    """处理单个账号的红色跑任务"""
    # 使用统一的会话管理器创建认证会话
    login_token = login_wrapper(account, password)
    if login_token:
        # 报名耐力跑
        safe_execute(
                lambda: sign_up(account),
                logger_name="redrun",
                error_handler=auth_error_handler,
                context={"username": account, "operation": "sign_up"}
            )
        
        # 切换跑步模式
        if case == "报名加跑步":
            # 开始跑步并获取跑步id
            challenge_id = safe_execute(
                lambda: start(account),
                logger_name="redrun",
                error_handler=auth_error_handler,
                context={"username": account, "operation": "start_run"}
            )
            
            if challenge_id:
                # 设置等待时间
                wait_time(account)
                # 结束跑步 - 只有成功才会记录完成状态
                success = safe_execute(
                    lambda: finish(challenge_id, account),
                    logger_name="redrun",
                    error_handler=auth_error_handler,
                    context={"username": account, "operation": "finish_run"}
                )
                if success:
                    logger.info(f"账号 {account} 红色跑流程完成")
                else:
                    logger.warning(f"账号 {account} 红色跑流程未完成")
    
    # 退出登录
    logout_wrapper(account)


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='红色跑处理程序')
    parser.add_argument('--manual-inject', action='store_true', help='启用手动注入模式')
    parser.add_argument('--test-data', type=str, default='[["24405010421", "24405010421"]]', 
                       help='手动注入的测试数据，JSON格式，例如: \"[[\"账号1\", \"密码1\"], [\"账号2\", \"密码2\"]]\"')
    parser.add_argument('--max-workers', type=int, default=5, help='最大线程数')
    return parser.parse_args()

def preprocess_accounts(accounts):
    """预处理账号数据，去重并确保每个账号只出现一次"""
    seen_accounts = set()
    unique_accounts = []
    
    for account, password in accounts:
        if account not in seen_accounts:
            seen_accounts.add(account)
            unique_accounts.append((account, password))
        else:
            logger.warning(f"发现重复账号 {account}，已跳过")
    
    logger.info(f"账号去重后数量: {len(unique_accounts)}")
    return unique_accounts

if __name__ == '__main__':
    # 解析命令行参数
    args = parse_arguments()
    
    # 创建队列
    q = queue.Queue()
    
    try:
        # 根据参数决定数据来源
        if args.manual_inject:
            logger.info("使用手动注入模式")
            try:
                # 解析测试数据
                test_accounts = json.loads(args.test_data)
                if not isinstance(test_accounts, list):
                    raise ValueError("测试数据必须是列表格式")
                
                # 验证数据格式
                for item in test_accounts:
                    if not isinstance(item, list) or len(item) != 2:
                        raise ValueError("每个账号数据必须是[账号, 密码]格式")
                
                accounts = preprocess_accounts(test_accounts)
                logger.info(f"手动注入的账号数量: {len(accounts)}")
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"测试数据格式错误: {str(e)}")
                exit(1)
        else:
            logger.info("使用正常模式")
            # 获取需要红色跑的用户账号
            accounts = safe_execute(
                lambda: filter.get_red_run_users(),
                default_return=[],
                logger_name="redrun",
                context={"operation": "get_red_run_users"}
            )
            accounts = preprocess_accounts(accounts)
            logger.info(f"从表格获取到需要红色跑的用户数量: {len(accounts)}")
        
        if not accounts:
            logger.info("没有需要处理的账号")
            exit()
        
        # 使用多线程处理多个账号
        max_workers = min(args.max_workers, len(accounts))  # 最多使用指定线程数，避免过多并发
        logger.info(f"使用 {max_workers} 个线程处理 {len(accounts)} 个账号")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 为每个账号提交一个任务
            futures = []
            for account, password in accounts:
                future = executor.submit(process_single_account, account, password, "报名加跑步")
                futures.append(future)
            
            # 等待所有任务完成
            for future in futures:
                try:
                    future.result()  # 获取结果，如果有异常会抛出
                except Exception as e:
                    logger.error(f"账号处理异常: {str(e)}")
        
        logger.info("所有账号处理完成")
    finally:
        # 清理所有会话
        session_manager.cleanup_all_sessions()