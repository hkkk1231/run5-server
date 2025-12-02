import json
import queue
import random
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Callable, List, Optional, Tuple
import sys

import requests

# 统一使用 main_code 作为导入根目录，兼容直接运行和 -m 方式
CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[2]  # .../main_code
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

from spider.package.core.common_utils import setup_logger
from spider.package.data.filter import get_red_run_users_with_path
from spider.package.network import get_headers
from paths import (
    RED_RUN_COMPLETION_FILE,
    RED_RUN_ERROR_PASSWORD_FILE,
    RED_RUN_LOG_FILE,
    ensure_dir,
)

# 配置日志与记录文件路径
ensure_dir(RED_RUN_LOG_FILE.parent)
ensure_dir(RED_RUN_COMPLETION_FILE.parent)
ensure_dir(RED_RUN_ERROR_PASSWORD_FILE.parent)
logger = setup_logger("redrun", str(RED_RUN_LOG_FILE))
_COMPLETION_FILE_LOCK = Lock()
_ERROR_PASSWORD_FILE_LOCK = Lock()


@dataclass
class AccountPanelState:
    account: str
    password: str
    status: str = "等待开始"
    elapsed: int = 0  # 秒
    progress: float = 0.0  # 0.0 ~ 1.0
    result: Optional[str] = None  # success / already_completed / password_error / failed


class BatchPanel:
    """
    批次面板：负责在终端上以固定区域展示一批账号的进度。
    """

    def __init__(self, batch_index: int, total_batches: int, accounts: List[Tuple[str, str]]) -> None:
        self.batch_index = batch_index
        self.total_batches = total_batches
        self._lock = Lock()
        self._states: List[AccountPanelState] = [
            AccountPanelState(account=str(acc), password=str(pw))
            for acc, pw in accounts
        ]
        self._initialized = False
        self._height = 0

    def update(self, index: int, **fields: object) -> None:
        """线程安全地更新某个账号在面板中的信息"""
        with self._lock:
            if not (0 <= index < len(self._states)):
                return
            state = self._states[index]
            for key, value in fields.items():
                if hasattr(state, key):
                    setattr(state, key, value)

    def snapshot(self) -> List[AccountPanelState]:
        """获取当前批次所有账号的状态快照"""
        with self._lock:
            return list(self._states)

    def render(self) -> None:
        """
        在终端中以固定区域方式渲染当前批次面板：
        - 首次调用：顺序打印标题行 + 各账号行；
        - 后续调用：光标移动回面板顶部，原地覆盖更新，不新增新行。
        """
        # 构造展示文本时尽量缩短锁持有时间
        with self._lock:
            states = list(self._states)
            batch_index = self.batch_index
            total_batches = self.total_batches

        header = f"批次 {batch_index}/{total_batches} | 账号数：{len(states)}"
        lines = [header]

        for s in states:
            mins, secs = divmod(s.elapsed, 60)
            progress_percent = int(s.progress * 100)
            line = (
                f"{s.account} ({s.password}) | "
                f"耗时: {mins:02d}:{secs:02d} | "
                f"进度: {progress_percent:3d}% | "
                f"状态: {s.status}"
            )
            lines.append(line)

        # 非交互终端（例如被重定向到文件）时，退化成简单打印
        is_tty = sys.stdout.isatty()

        if not self._initialized:
            for line in lines:
                print(line)
            sys.stdout.flush()
            self._height = len(lines)
            self._initialized = True
            return

        if not is_tty:
            # 在非 TTY 环境中不做复杂的光标控制，避免产生奇怪的转义符
            for line in lines:
                print(line)
            sys.stdout.flush()
            self._height = len(lines)
            return

        # 终端模式：光标回到面板顶部，逐行覆盖
        sys.stdout.write(f"\033[{self._height}F")
        for line in lines:
            sys.stdout.write("\033[2K")  # 清空当前行
            sys.stdout.write(line + "\n")
        sys.stdout.flush()
        self._height = len(lines)

    def build_summary(self) -> dict:
        """统计当前批次各类结果数量，用于日志摘要"""
        summary = {
            "total": 0,
            "success": 0,
            "already_completed": 0,
            "password_error": 0,
            "failed": 0,
        }
        with self._lock:
            for state in self._states:
                summary["total"] += 1
                if state.result == "success":
                    summary["success"] += 1
                elif state.result == "already_completed":
                    summary["already_completed"] += 1
                elif state.result == "password_error":
                    summary["password_error"] += 1
                elif state.result:
                    summary["failed"] += 1
        return summary


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


def _load_error_passwords():
    """读取密码错误账号记录，返回 {account: {password, error_time}}"""
    if not RED_RUN_ERROR_PASSWORD_FILE.exists():
        try:
            RED_RUN_ERROR_PASSWORD_FILE.write_text("{}", encoding="utf-8")
        except OSError as exc:
            logger.error(f"初始化 red_error_password.json 失败：{exc}")
        return {}

    try:
        with RED_RUN_ERROR_PASSWORD_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
            if isinstance(data, dict):
                return data
    except json.JSONDecodeError:
        logger.warning("red_error_password.json 格式异常，已重置")
        try:
            RED_RUN_ERROR_PASSWORD_FILE.write_text("{}", encoding="utf-8")
        except OSError as exc:
            logger.error(f"重置 red_error_password.json 失败：{exc}")
    except OSError as exc:
        logger.error(f"读取 red_error_password.json 失败：{exc}")
    return {}


def _save_error_passwords(data):
    """保存密码错误账号记录"""
    try:
        with RED_RUN_ERROR_PASSWORD_FILE.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
    except OSError as exc:
        logger.error(f"写入 red_error_password.json 失败：{exc}")


def mark_error_password(account, password):
    """记录密码错误账号到 red_error_password.json"""
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _ERROR_PASSWORD_FILE_LOCK:
        records = _load_error_passwords()
        records[str(account)] = {
            "password": str(password),
            "error_time": error_time,
        }
        _save_error_passwords(records)
    logger.info(f"{account} 已记录为密码错误账号")


def login(session: requests.Session,
          username: str,
          inner_password: str,
          update_status: Optional[Callable[..., None]] = None) -> Optional[str]:
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
        if update_status:
            update_status(status="登录中")
        login_respond = session.post(json=data, url=login_url, timeout=10)
        login_respond.raise_for_status()
        payload = login_respond.json()
    except requests.RequestException as exc:
        logger.error(f"{username} 登录失败：{exc}")
        if update_status:
            update_status(status="登录异常", result="failed")
        return None
    except ValueError:
        logger.error(f"{username} 登录响应解析失败")
        if update_status:
            update_status(status="登录响应解析失败", result="failed")
        return None

    msg = payload.get("msg")
    if msg == "用户不存在/密码错误":
        logger.info(f"{username} 的密码错误")
        mark_error_password(username, inner_password)
        if update_status:
            update_status(status="密码错误", result="password_error", progress=1.0)
        return None

    token = payload.get("token")
    if not token:
        logger.error(f"{username} 登录成功但未返回 token")
        if update_status:
            update_status(status="登录失败（无token）", result="failed")
        return None

    if update_status:
        update_status(status="登录成功", progress=0.1)
    return token


def sign_up(session: requests.Session,
            update_status: Optional[Callable[..., None]] = None) -> None:
    # 请求报名页面url
    sign_url = "https://lb.hnfnu.edu.cn/school/competition"
    data = {"competitionId": 38, "competitionName": "环校跑"}
    try:
        if update_status:
            update_status(status="报名中")
        session.post(json=data, url=sign_url, headers=session.headers, timeout=10)
        logger.debug("报名请求已发送")
    except requests.RequestException as exc:
        logger.warning(f"报名环校跑失败：{exc}")
        if update_status:
            update_status(status="报名失败", result="failed")
    else:
        if update_status:
            update_status(status="报名完成", progress=0.15)


def start(session: requests.Session,
          account: str,
          update_status: Optional[Callable[..., None]] = None) -> Optional[int]:
    # 开始跑步url
    start_url = "https://lb.hnfnu.edu.cn/school/challenges"
    data = {}
    try:
        if update_status:
            update_status(status="准备开始挑战")
        start_respond = session.post(json=data, url=start_url, headers=session.headers, timeout=10)
        start_respond.raise_for_status()
        respond_json = start_respond.json()
    except requests.RequestException as exc:
        logger.error(f"{account} 开始跑步失败：{exc}")
        if update_status:
            update_status(status="开始跑步失败（网络异常）", result="failed")
        return None
    except ValueError:
        logger.error(f"{account} 开始跑步响应解析失败")
        if update_status:
            update_status(status="开始跑步响应解析失败", result="failed")
        return None

    if respond_json.get("msg") == "今日已完成挑战,请明天再来":
        logger.info(f"{account} 今日已完成挑战")
        if update_status:
            update_status(status="今日已完成", progress=1.0, result="already_completed")
        return None

    respond_data = respond_json.get("data") or {}
    challenge_id = respond_data.get("challengeId")
    if not challenge_id:
        logger.warning(f"{account} 开始跑步接口未返回 challengeId")
        if update_status:
            update_status(status="开始跑步失败", result="failed")
        return None

    if update_status:
        update_status(status="挑战进行中", progress=0.2)
    return challenge_id


def wait_time(account: str,
              update_status: Optional[Callable[..., None]] = None,
              mintime: int = 1551,
              maxtime: int = 1682) -> int:
    """
    等待模拟跑步时长。
    - 不再向日志中高频写入倒计时信息；
    - 通过 update_status 回调更新面板上的耗时和进度。
    """
    seconds = random.randint(mintime, maxtime)
    start_time = time.time()
    if update_status:
        update_status(status="跑步中", elapsed=0, progress=0.2)

    last_reported_second = -1
    while True:
        elapsed_time = time.time() - start_time
        elapsed_int = int(elapsed_time)
        remaining = seconds - elapsed_int
        if remaining <= 0:
            break
        if update_status and elapsed_int != last_reported_second:
            last_reported_second = elapsed_int
            progress = min(elapsed_time / seconds, 0.99)
            update_status(elapsed=elapsed_int, progress=progress)
        time.sleep(1)

    if update_status:
        update_status(elapsed=seconds, progress=1.0)
    return seconds


def finish(session: requests.Session,
           challenge_id: int,
           account: str,
           update_status: Optional[Callable[..., None]] = None) -> bool:
    # 传入挑战id，结束跑步url
    finish_url = f"https://lb.hnfnu.edu.cn/school/challenges?challengeId={challenge_id}"
    try:
        respond = session.put(url=finish_url, headers=session.headers, timeout=10)
        respond.raise_for_status()
        payload = respond.json()
    except requests.RequestException as exc:
        logger.error(f"{account} 结束跑步失败：{exc}")
        if update_status:
            update_status(status="结束跑步失败（网络异常）", result="failed")
        return False
    except ValueError:
        logger.error(f"{account} 结束跑步响应解析失败")
        if update_status:
            update_status(status="结束跑步响应解析失败", result="failed")
        return False

    msg = payload.get("msg", "")
    logger.info(f"{account} 结束结果：{msg}")
    if msg == "操作成功":
        if update_status:
            update_status(status="已完成", progress=1.0, result="success")
        return True

    if update_status:
        update_status(status=f"结束失败：{msg}", result="failed", progress=1.0)
    return False


def logout(session: requests.Session) -> None:
    # 退出登录
    logout_url = "https://lb.hnfnu.edu.cn/logout"
    logout_herders = {"custom-header": "{}", "Content-Length": "0", "Content-Type": "application/json"}
    try:
        session.post(headers=logout_herders, url=logout_url, timeout=5)
    except requests.RequestException as exc:
        logger.debug(f"退出登录失败：{exc}")


def process_account(account: str,
                    password: str,
                    panel: Optional[BatchPanel] = None,
                    index: Optional[int] = None,
                    case: str = "报名加跑步") -> None:
    session = requests.Session()

    def update_status(**fields: object) -> None:
        if panel is not None and index is not None:
            panel.update(index, **fields)

    try:
        headers = get_headers()
        session.headers.update(headers)
        update_status(status="等待开始", progress=0.0)
        login_token = login(session, account, password, update_status=update_status)
        if not login_token:
            return

        session.headers.update({"Authorization": f"Bearer {login_token}"})
        sign_up(session, update_status=update_status)

        if case == "报名加跑步":
            challenge_id = start(session, account, update_status=update_status)
            if challenge_id:
                run_time = wait_time(account, update_status=update_status)
                if finish(session, challenge_id, account, update_status=update_status):
                    record_completion(account, password, session, run_time)
    except Exception as exc:
        logger.error(f"{account} 处理失败：{exc}")
        update_status(status="处理异常", result="failed")
    finally:
        logout(session)


def main(q: queue.Queue,
         case: str = "报名加跑步",
         batch_size: int = 5) -> None:
    # 预先计算总批次数，用于面板标题展示
    try:
        total_tasks = q.qsize()
    except NotImplementedError:
        total_tasks = 0
    total_batches = (total_tasks + batch_size - 1) // batch_size if total_tasks else 0

    batch_index = 0
    while True:
        batch: List[Tuple[str, str]] = []
        while len(batch) < batch_size:
            try:
                batch.append(q.get_nowait())
            except queue.Empty:
                break

        if not batch:
            break

        batch_index += 1
        batch_size_actual = len(batch)
        if total_batches == 0:
            logger.info(f"开始处理批次，账号数：{batch_size_actual}")
        else:
            logger.info(f"开始处理批次 {batch_index}/{total_batches}，账号数：{batch_size_actual}")

        panel = BatchPanel(batch_index=batch_index, total_batches=max(total_batches, batch_index), accounts=batch)

        with ThreadPoolExecutor(max_workers=batch_size_actual) as executor:
            futures = [
                executor.submit(process_account, account, password, panel, idx, case)
                for idx, (account, password) in enumerate(batch)
            ]

            # 实时刷新当前批次的终端面板（固定区域原地更新）
            while True:
                panel.render()
                if all(future.done() for future in futures):
                    break
                time.sleep(1)

            # 确保异常可以被记录到日志中
            for future in futures:
                try:
                    future.result()
                except Exception as exc:
                    logger.error(f"批次任务异常：{exc}")

        # 批次结束后定格面板，并输出一条干净的批次摘要日志
        panel.render()
        summary = panel.build_summary()
        if total_batches == 0:
            logger.info(
                f"批次处理完成：总数 {summary['total']}，成功 {summary['success']}，"
                f"今日已完成 {summary['already_completed']}，密码错误 {summary['password_error']}，"
                f"失败 {summary['failed']}"
            )
        else:
            logger.info(
                f"批次 {batch_index}/{total_batches} 处理完成：总数 {summary['total']}，成功 {summary['success']}，"
                f"今日已完成 {summary['already_completed']}，密码错误 {summary['password_error']}，"
                f"失败 {summary['failed']}"
            )


if __name__ == '__main__':
    print("脚本开始运行...")
    # 创建队列
    q = queue.Queue()
    # 获取数据（包含途径字段）
    account_password_path_list = get_red_run_users_with_path()

    # 基于当前时间和途径字段过滤需要跳过的账号
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    in_skip_window = 18 * 60 + 30 <= current_minutes <= 21 * 60 + 30

    skipped_due_to_path_and_time: List[Tuple[str, str]] = []
    account_passwords: List[Tuple[str, str]] = []

    for item in account_password_path_list:
        # 兼容性处理：如果没有途径字段，则按原逻辑只取前两个元素
        if len(item) >= 3:
            account, password, path = item[0], item[1], item[2]
        else:
            account, password = item[0], item[1]
            path = None

        if in_skip_window and path == "追逐":
            skipped_due_to_path_and_time.append((str(account), str(password)))
            continue

        account_passwords.append((str(account), str(password)))

    if skipped_due_to_path_and_time:
        skipped_accounts_str = ", ".join(acc for acc, _ in skipped_due_to_path_and_time)
        msg = (
            f"当前时间 {now.strftime('%H:%M')} 处于 18:30-21:30，"
            f"根据途径字段为“追逐”跳过以下账号：{skipped_accounts_str}"
        )
        print(msg)
        logger.info(msg)

    # 读取并跳过历史密码错误账号
    error_password_records = _load_error_passwords()
    if error_password_records:
        before_filter_count = len(account_passwords)
        account_passwords = [
            (account, password)
            for account, password in account_passwords
            if str(account) not in error_password_records
        ]
        skipped_count = before_filter_count - len(account_passwords)
        if skipped_count > 0:
            print(f"已根据 red_error_password.json 跳过 {skipped_count} 个密码错误账号")
            logger.info(f"已根据 red_error_password.json 跳过 {skipped_count} 个密码错误账号")

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
