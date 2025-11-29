import json
import queue
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock

import requests

from main_code.spider.package.core.common_utils import setup_logger
from main_code.spider.package.data.filter import get_red_run_users
from main_code.spider.package.network import get_headers
from paths import RED_RUN_COMPLETION_FILE, RED_RUN_LOG_FILE, ensure_dir

# 配置日志与记录文件路径
ensure_dir(RED_RUN_LOG_FILE.parent)
ensure_dir(RED_RUN_COMPLETION_FILE.parent)
logger = setup_logger("redrun", str(RED_RUN_LOG_FILE))
_COMPLETION_FILE_LOCK = Lock()


def _load_completion_records():
    """读取已完成记录文件，返回列表"""
    if not RED_RUN_COMPLETION_FILE.exists():
        RED_RUN_COMPLETION_FILE.write_text("[]", encoding="utf-8")
        return []
    try:
        with RED_RUN_COMPLETION_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, list):
                return data
    except json.JSONDecodeError:
        logger.warning("redrun_complete.json 格式异常，已重置")
    return []


def _append_completion_record(record):
    """线程安全地追加完成记录"""
    with _COMPLETION_FILE_LOCK:
        records = _load_completion_records()
        records.append(record)
        with RED_RUN_COMPLETION_FILE.open("w", encoding="utf-8") as file:
            json.dump(records, file, ensure_ascii=False, indent=2)


def _fetch_student_name(session):
    """从跑步记录接口获取学生姓名"""
    try:
        record_url = "https://lb.hnfnu.edu.cn/school/student/getMyLongMarchList"
        response = session.get(record_url, headers=session.headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        rows = data.get("rows") or []
        if rows:
            return rows[0].get("studentName") or ""
    except requests.RequestException as exc:
        logger.warning(f"查询姓名失败：{exc}")
    except ValueError:
        logger.warning("查询姓名时解析响应失败")
    return ""


def record_completion(account, password, session, run_time):
    """将成功完成的账号信息写入 redrun_complete.json"""
    student_name = _fetch_student_name(session)
    record = {
        "account": account,
        "password": password,
        "name": student_name,
        "run_time": run_time,
        "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    _append_completion_record(record)
    logger.info(f"{account} 已记录完成信息")

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
    try:
        login_respond = session.post(json=data, url=login_url, timeout=10)
        login_respond.raise_for_status()
        payload = login_respond.json()
    except requests.RequestException as exc:
        logger.error(f"{username} 登录失败：{exc}")
        return False
    except ValueError:
        logger.error(f"{username} 登录响应解析失败")
        return False

    msg = payload.get("msg")
    if msg == "用户不存在/密码错误":
        logger.info(f"{username} 的密码错误")
        return False
    return payload.get("token")


def sign_up(session):
    # 请求报名页面url
    sign_url = "https://lb.hnfnu.edu.cn/school/competition"
    data = {"competitionId": 38, "competitionName": "环校跑"}
    try:
        session.post(json=data, url=sign_url, headers=session.headers, timeout=10)
        logger.debug("报名请求已发送")
    except requests.RequestException as exc:
        logger.warning(f"报名环校跑失败：{exc}")

def start(session, account):
    # 开始跑步url
    start_url = "https://lb.hnfnu.edu.cn/school/challenges"
    data = {}
    try:
        start_respond = session.post(json=data, url=start_url, headers=session.headers, timeout=10)
        start_respond.raise_for_status()
        respond_json = start_respond.json()
    except requests.RequestException as exc:
        logger.error(f"{account} 开始跑步失败：{exc}")
        return None
    except ValueError:
        logger.error(f"{account} 开始跑步响应解析失败")
        return None

    if respond_json.get("msg") == "今日已完成挑战,请明天再来":
        logger.info(f"{account} 今日已完成挑战")
        return None

    respond_data = respond_json.get("data") or {}
    challenge_id = respond_data.get("challengeId")
    if not challenge_id:
        logger.warning(f"{account} 开始跑步接口未返回 challengeId")
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
            logger.info(timer)
        time.sleep(1)
    return seconds


def finish(session, challenge_id, account):
    # 传入挑战id，结束跑步url
    finish_url = f"https://lb.hnfnu.edu.cn/school/challenges?challengeId={challenge_id}"
    try:
        respond = session.put(url=finish_url, headers=session.headers, timeout=10)
        respond.raise_for_status()
        payload = respond.json()
    except requests.RequestException as exc:
        logger.error(f"{account} 结束跑步失败：{exc}")
        return False
    except ValueError:
        logger.error(f"{account} 结束跑步响应解析失败")
        return False

    msg = payload.get("msg", "")
    logger.info(f"{account} 结束结果：{msg}")
    return msg == "操作成功"

def logout(session):
    # 退出登录
    logout_url = "https://lb.hnfnu.edu.cn/logout"
    logout_herders = {"custom-header": "{}", "Content-Length": "0", "Content-Type": "application/json"}
    try:
        session.post(headers=logout_herders, url=logout_url, timeout=5)
    except requests.RequestException as exc:
        logger.debug(f"退出登录失败：{exc}")

def process_account(account, password, case="报名加跑步"):
    session = requests.Session()
    try:
        headers = get_headers()
        session.headers.update(headers)
        login_token = login(session, account, password)
        if not login_token:
            return

        session.headers.update({"Authorization": f"Bearer {login_token}"})
        sign_up(session)

        if case == "报名加跑步":
            challenge_id = start(session, account)
            if challenge_id:
                run_time = wait_time(account)
                if finish(session, challenge_id, account):
                    record_completion(account, password, session, run_time)
    except Exception as exc:
        logger.error(f"{account} 处理失败：{exc}")
    finally:
        logout(session)


def main(q, case="报名加跑步", batch_size=5):
    while True:
        batch = []
        while len(batch) < batch_size:
            try:
                batch.append(q.get_nowait())
            except queue.Empty:
                break

        if not batch:
            break

        batch_size_actual = len(batch)
        logger.info(f"开始处理批次，账号数：{batch_size_actual}")
        with ThreadPoolExecutor(max_workers=batch_size_actual) as executor:
            futures = [
                executor.submit(process_account, account, password, case)
                for account, password in batch
            ]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as exc:
                    logger.error(f"批次任务异常：{exc}")
        logger.info("批次处理完成")


if __name__ == '__main__':
    print("脚本开始运行...")
    # 创建队列
    q = queue.Queue()
    # 获取数据
    # account_passwords = [["24404010309","24404010309"]]
    account_passwords = get_red_run_users()
    if not account_passwords:
        print("未从 red_run 过滤中获取到学号数据")
    else:
        print(f"已获取 {len(account_passwords)} 位红色跑用户")
    for account_password in account_passwords:
        q.put(account_password)
    
    print(f"队列中有 {q.qsize()} 个任务")
    print("开始批次执行...")
    main(q)
    print("任务完成")
