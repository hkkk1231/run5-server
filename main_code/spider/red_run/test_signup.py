# 专注测试报名功能的Python文件
import requests
import logging
import time
import random
import json

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler("test_signup_log.txt", mode='w'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def get_headers():
    """获取请求头"""
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Referer": "https://lb.hnfnu.edu.cn/",
    }

def login(session, username, password):
    """
    简化的登录函数，参考历史版本和login.py
    """
    # 登录url
    login_url = "https://lb.hnfnu.edu.cn/login"
    
    # 登录数据
    data = {
        "username": username,
        "password": password,
        "code": "",
        "uuid": "",
    }
    
    logger.info(f"正在登录账号: {username}")
    
    try:
        # 提交登录数据
        login_response = session.post(json=data, url=login_url, headers=session.headers)
        login_response.raise_for_status()  # 检查HTTP错误
        
        # 解析响应
        response_json = login_response.json()
        msg = response_json.get("msg", "")
        token = response_json.get("token")
        
        # 处理登录结果
        if msg == "操作成功":
            logger.info(f"账号 {username} 登录成功")
            
            # 检查token是否存在
            if not token:
                logger.error(f"账号 {username} 登录成功但未获取到token")
                return False
            
            # 更新会话的Authorization头
            session.headers.update({
                "Authorization": f"Bearer {token}"
            })
            logger.debug(f"账号 {username} Authorization头已更新")
            
            return True
        else:
            logger.warning(f"账号 {username} 登录失败: {msg}")
            return False
            
    except Exception as e:
        logger.error(f"账号 {username} 登录请求异常: {str(e)}")
        return False

def test_signup(session, account):
    """
    专注测试报名功能，参考当前red_run.py的sign_up函数
    """
    # 请求报名页面url
    sign_url = "https://lb.hnfnu.edu.cn/school/competition"
    data = {"competitionId": 37, "competitionName": "环校跑"}
    
    try:
        # 提交报名数据
        logger.info(f"账号 {account} 开始报名环校跑")
        logger.debug(f"报名URL: {sign_url}")
        logger.debug(f"报名数据: {data}")
        
        sign_response = session.post(json=data, url=sign_url, headers=session.headers)
        logger.debug(f"账号 {account} 报名响应状态码: {sign_response.status_code}")
        
        sign_response.raise_for_status()  # 检查HTTP错误
        
        # 解析报名响应
        response_json = sign_response.json()
        msg = response_json.get("msg", "")
        
        logger.info(f"账号 {account} 报名响应消息: {msg}")
        logger.debug(f"账号 {account} 报名响应详情: {response_json}")
        
        # 检查报名结果
        if msg == "操作成功" or "报名成功" in msg:
            logger.info(f"账号 {account} 环校跑报名成功")
            return True
        elif "已参加该竞赛" in msg or "已报名" in msg:
            logger.info(f"账号 {account} 已经报名过环校跑")
            return True
        else:
            logger.warning(f"账号 {account} 环校跑报名失败: {msg}")
            return False
            
    except Exception as e:
        logger.error(f"账号 {account} 报名请求异常: {str(e)}")
        logger.debug(f"账号 {account} 报名异常详情", exc_info=True)
        return False

def logout(session):
    """
    退出登录，清理会话状态
    """
    logout_url = "https://lb.hnfnu.edu.cn/logout"
    
    # 准备退出登录的请求头
    logout_headers = {
        "custom-header": "{}", 
        "Content-Length": "0", 
        "Content-Type": "application/json"
    }
    
    try:
        # 发送退出登录请求
        response = session.post(url=logout_url, headers=logout_headers)
        response.raise_for_status()
        logger.info("已成功退出登录")
        return True
    except Exception as e:
        logger.warning(f"退出登录请求失败: {str(e)}")
        return False

def process_account(account, password):
    """
    处理单个账号的报名测试
    """
    logger.info(f"开始处理账号: {account}")
    
    # 创建会话
    session = requests.Session()
    
    # 获取ua并更新请求头
    headers = get_headers()
    session.headers.update(headers)
    
    # 登录
    login_success = login(session, account, password)
    if login_success:
        # 测试报名
        signup_success = test_signup(session, account)
        if signup_success:
            logger.info(f"账号 {account} 报名测试成功")
        else:
            logger.warning(f"账号 {account} 报名测试失败")
    else:
        logger.error(f"账号 {account} 登录失败，跳过报名测试")
    
    # 退出登录
    logout(session)
    
    # 关闭会话
    session.close()
    
    logger.info(f"账号 {account} 处理完成")

def main():
    """
    主函数，使用内置测试数据
    """
    logger.info("="*50)
    logger.info("开始执行报名测试程序")
    logger.info("="*50)
    
    # 内置测试数据
    test_accounts = [
        ["24405010421", "24405010421"], 
        ["24405010422", "24405010422"]
    ]
    
    logger.info(f"使用内置测试数据，共 {len(test_accounts)} 个账号")
    
    # 处理每个账号
    for account, password in test_accounts:
        try:
            process_account(account, password)
            # 账号之间添加随机延迟，避免请求过于频繁
            time.sleep(random.uniform(1, 3))
        except Exception as e:
            logger.error(f"处理账号 {account} 时发生异常: {str(e)}")
            continue
    
    logger.info("="*50)
    logger.info("报名测试程序执行完成")
    logger.info("="*50)

if __name__ == '__main__':
    main()