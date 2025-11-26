import os
import sys
import time
import requests
import random
import queue
from concurrent.futures import ThreadPoolExecutor

# 统一使用绝对导入，基于项目根目录的现代pathlib方式
# 项目根目录：run5-server
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 统一导入：所有模块都使用绝对导入
from main_code.spider.package.network.get_headers import get_headers
from main_code.spider.package.data import filter
from main_code.spider.package.auth.login import create_authenticated_session
from main_code.spider.package.auth.session_manager import session_manager
from main_code.spider.package.core.common_utils import setup_logger, authenticated_operation
from main_code.spider.package.core.error_handler import safe_execute, auth_error_handler

# 统一的路径配置
from paths import SPIDER_LOGS_DIR

logger = setup_logger("redrun", str(SPIDER_LOGS_DIR / "redrun_log.txt"))

def login_wrapper(username, inner_password):
    # 使用统一的会话管理器创建认证会话
    headers = get_headers()
    session = create_authenticated_session(username, inner_password, headers=headers)
    
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
    
    # 提交报名数据
    session.post(json=data, url=sign_url, headers=session.headers)
    return True

@authenticated_operation
def start(account):
    # 从会话管理器获取会话
    session = session_manager.get_session(account)
    if not session:
        logger.error(f"无法获取账号 {account} 的会话")
        return False
    
    # 报名
    if not sign_up(account):
        logger.error(f"账号 {account} 报名失败")
        return False
    
    # 请求跑步页面url
    run_url = "https://lb.hnfnu.edu.cn/school/run"
    response = session.get(run_url, headers=session.headers)
    # 解析跑步页面数据
    data = filter.filter_data(response.text)
    # 提交跑步数据
    session.post(json=data, url=run_url, headers=session.headers)
    return True


def wait_time(account, mintime=1551, maxtime=1682):
    seconds = random.randint(mintime, maxtime)
    start_time = time.time()
    while True:
        elapsed_time = time.time() - start_time
        remaining = seconds - int(elapsed_time)
        if remaining <= 0:
            break
        if int(elapsed_time) % 60 == 0:
            mins, secs = divmod(remaining, 60)
            timer = f"{account} 还需：{mins:02d}min"
            logger.info(timer)
        time.sleep(1)


@authenticated_operation
def finish(challenge_id, account):
    # 从会话管理器获取会话
    session = session_manager.get_session(account)
    if not session:
        logger.error(f"无法获取账号 {account} 的会话")
        return False
    
    # 传入挑战id，结束跑步url
    finish_url = f"https://lb.hnfnu.edu.cn/school/challenges?challengeId={challenge_id}"
    # 提交结束跑步请求
    start_resepond = session.put(url=finish_url, headers=session.headers)
    logger.info(f"{account} 结束结果：{start_resepond.json()['msg']}")
    return True

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
            logger=logger,
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
                logger=logger,
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
            logger=logger,
            error_handler=auth_error_handler,
            context={"username": account, "operation": "sign_up"}
        )
        
        # 切换跑步模式
        if case == "报名加跑步":
            # 开始跑步并获取跑步id
            challenge_id = safe_execute(
                lambda: start(account),
                logger=logger,
                error_handler=auth_error_handler,
                context={"username": account, "operation": "start_run"}
            )
            
            if challenge_id:
                # 设置等待时间
                wait_time(account)
                # 结束跑步
                safe_execute(
                    lambda: finish(challenge_id, account),
                    logger=logger,
                    error_handler=auth_error_handler,
                    context={"username": account, "operation": "finish_run"}
                )
    
    # 退出登录
    logout_wrapper(account)


if __name__ == '__main__':
    # 创建队列
    q = queue.Queue()
    
    try:
        # 使用新的main函数，它会自动调用过滤函数获取需要红色跑的用户
        with ThreadPoolExecutor(max_workers=6) as executor:
            for _ in range(6):
                executor.submit(main, q)
    finally:
        # 清理所有会话
        session_manager.cleanup_all_sessions()