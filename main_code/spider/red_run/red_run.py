import time
import requests
from main_code.spider.package.network import get_headers
from main_code.spider.package.data import read_excel
import random
import queue
import logging
from concurrent.futures import ThreadPoolExecutor

# 配置日志，将日志信息写入文件
logging.basicConfig(
    level=logging.INFO,
    force=True,
    format='%(asctime)s- %(message)s',
    datefmt='%H:%M',  # 设置时间格式为 24 小时制的小时和分钟
    handlers=[
        logging.FileHandler("main_code/spider/resource/logs/redrun_log.txt", mode='w'),
        logging.StreamHandler()
    ]
)

def login(session, username, inner_password):
    # 登录url
    login_url = "https://lb.hnfnu.edu.cn/login"
    # 登录数据
    data = {
        "username": f"{username}",
        "password": f"{inner_password}",
        "code": "",
        "uuid": "",
    }
    # 提交登录数据
    login_respond = session.post(json=data, url=login_url)
    msg = login_respond.json()["msg"]
    if msg == "用户不存在/密码错误":
        logging.info(f"{username}的密码错误")
        token = False
    else:
        # 获取token
        token = login_respond.json().get("token")
    return token


def sign_up(session):
    # 请求报名页面url
    sign_url = "https://lb.hnfnu.edu.cn/school/competition"
    data = {"competitionId": 38, "competitionName": "环校跑"}
    # 提交报名数据
    session.post(json=data, url=sign_url, headers=session.headers)

def start(session, account):
    # 开始跑步url
    start_url = "https://lb.hnfnu.edu.cn/school/challenges"
    data = {}
    # 提交开始跑步请求
    start_resepond = session.post(json=data, url=start_url, headers=session.headers)
    resepond_json = start_resepond.json()
    if resepond_json["msg"] == "今日已完成挑战,请明天再来":
        logging.info(f"{account}的今天跑过了")
    resepond_data = resepond_json["data"]
    challenge_id = resepond_data["challengeId"]
    return challenge_id


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
            logging.info(timer)
        time.sleep(1)


def finish(session, challenge_id, account):
    # 传入挑战id，结束跑步url
    finish_url = f"https://lb.hnfnu.edu.cn/school/challenges?challengeId={challenge_id}"
    # 提交结束跑步请求
    start_resepond = session.put(url=finish_url, headers=session.headers)
    logging.info(f"{account} 结束结果：{start_resepond.json()['msg']}")

def logout(session):
    # 退出登录
    logout_url = "https://lb.hnfnu.edu.cn/logout"
    logout_herders = {"custom-header": "{}", "Content-Length": "0", "Content-Type": "application/json"}
    session.post(headers=logout_herders, url=logout_url)

def main(q, case="报名加跑步"):
    while not q.empty():
        try:
            account, password = q.get_nowait()
            # 创建会话
            session = requests.Session()
            # 获取ua并更新请求头
            headers = get_headers()
            session.headers.update(headers)
            # 发送登录请求，并返回响应数据
            login_token = login(session, account, password)
            if login_token:
                # 添加token到请求头
                session.headers.update({
                    "Authorization": f"Bearer {login_token}"
                })
                # 报名耐力跑
                sign_up(session)
                # 切换跑步模式
                if case == "报名加跑步":
                    # 开始跑步并获取跑步id
                    challenge_id = start(session, account)
                    # 设置等待时间
                    wait_time(account)
                    # 结束跑步
                    finish(session, challenge_id, account)
            # 退出登录
            logout(session)
        except queue.Empty:
            break


if __name__ == '__main__':
    print("脚本开始运行...")
    # 创建队列
    q = queue.Queue()
    # 获取数据
    account_passwords = [["24404010309","24404010309"]]
    for account_password in account_passwords:
        q.put(account_password)
    
    print(f"队列中有 {q.qsize()} 个任务")

    with ThreadPoolExecutor(max_workers=1) as executor:
        print("提交任务到线程池...")
        future = executor.submit(main, q)
        print("等待任务完成...")
        future.result()
        print("任务完成")
