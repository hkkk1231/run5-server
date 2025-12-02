import logging
import random
from datetime import datetime
from pathlib import Path
from typing import List

import requests
import sys

CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[3]
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

from paths import RANK_RECORD_DIR, ensure_dir
from spider.package.auth.session_manager import session_manager
from spider.package.core.logger_manager import setup_logger
from spider.package.network.get_headers import get_headers

RANK_URL = "https://lb.hnfnu.edu.cn/school/challenges/endurance/challenge/rank"

TEST_ACCOUNTS: List[str] = [
    "24417010402",
    "24417030101",
    "24417030419",
    "24417030428",
    "24417040118",
]

logger = setup_logger("get_rank")


def _choose_test_account() -> str:
    return random.choice(TEST_ACCOUNTS)


def _get_today_file_path() -> Path:
    today_str = datetime.now().strftime("%Y-%m-%d")
    ensure_dir(RANK_RECORD_DIR)
    return RANK_RECORD_DIR / f"{today_str}.txt"


def fetch_rank_data() -> str:
    account = _choose_test_account()
    password = account
    headers = get_headers()

    session = session_manager.create_session(account, headers=headers)
    if not session:
        logger.error("创建会话失败")
        raise RuntimeError("创建会话失败")

    session = session_manager.login_session(account, password)
    if not session:
        logger.error("登录失败，无法获取排行榜")
        raise RuntimeError("登录失败，无法获取排行榜")

    try:
        response = session.get(RANK_URL, headers=session.headers, timeout=10)
        response.raise_for_status()
        logger.info("获取排行榜成功")
        return response.text
    except requests.exceptions.RequestException as exc:
        logger.error(f"获取排行榜请求失败: {exc}")
        raise
    finally:
        session_manager.logout_session(account)


def save_today_rank() -> Path:
    content = fetch_rank_data()
    file_path = _get_today_file_path()
    with file_path.open("w", encoding="utf-8") as file:
        file.write(content)
    logger.info(f"今日排行榜已保存到: {file_path}")
    return file_path


def main() -> None:
    save_today_rank()


if __name__ == "__main__":
    main()

