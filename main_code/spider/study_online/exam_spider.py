import requests
import json
import os
import sys
import logging
import ast
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 统一使用 main_code 作为导入根目录，兼容直接运行和 -m 方式
CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[2]  # .../main_code
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

# 使用统一的绝对路径配置
from paths import (
    EXAM_LOG,
    EXAM_2025_24_QUESTIONS_FILE,
    EXAM_2025_24_ANSWERS_FILE,
    EXAM_2025_25_QUESTIONS_FILE,
    EXAM_2025_25_ANSWERS_FILE,
)

# 统一导入：所有模块都使用绝对导入（以 spider 为顶级包）
from spider.package.network.get_headers import get_headers
from spider.package.data import filter
from spider.study_online import completion_status
from spider.package.auth.login import create_authenticated_session
from spider.package.auth.session_manager import session_manager
from spider.package.core.common_utils import AutoLoginBase, authenticated_operation, setup_logger
from spider.package.core.error_handler import retry_on_exception, safe_execute, auth_error_handler

# 设置日志
logger = setup_logger('exam', str(EXAM_LOG))


LOCAL_EXAM_CONFIGS: List[Dict[str, object]] = [
    {
        "name": "24级上册",
        "question_file": EXAM_2025_24_QUESTIONS_FILE,
        "answer_file": EXAM_2025_24_ANSWERS_FILE,
    },
    {
        "name": "25级上册",
        "question_file": EXAM_2025_25_QUESTIONS_FILE,
        "answer_file": EXAM_2025_25_ANSWERS_FILE,
    },
]


def _normalize_question_list(question_response: Dict[str, object]) -> List[Dict[str, object]]:
    """
    将题目列表规范化为可比较的结构，仅保留用于匹配的关键字段。
    """
    if not isinstance(question_response, dict):
        return []

    data_list = question_response.get("data") or []
    normalized: List[Dict[str, object]] = []

    for item in data_list:
        if not isinstance(item, dict):
            continue
        normalized.append(
            {
                "topicId": item.get("topicId"),
                "topicType": item.get("topicType"),
                "topicContent": item.get("topicContent"),
                "a": item.get("a"),
                "b": item.get("b"),
                "c": item.get("c"),
                "d": item.get("d"),
            }
        )

    return normalized


def match_exam_by_questions(
    current_question_response: Dict[str, object],
) -> Tuple[Optional[Path], Optional[str]]:
    """
    根据当前获取到的题目，与本地抓包题目进行匹配，返回对应的答案文件路径和年级名称。
    """
    current_normalized = _normalize_question_list(current_question_response)
    if not current_normalized:
        return None, None

    for config in LOCAL_EXAM_CONFIGS:
        question_file: Path = config["question_file"]  # type: ignore[assignment]

        try:
            with open(question_file, "r", encoding="utf-8") as f:
                local_question_response = json.load(f)
        except FileNotFoundError:
            logger.warning(f"本地题目文件不存在: {question_file}")
            continue
        except json.JSONDecodeError:
            logger.error(f"本地题目文件 JSON 格式错误: {question_file}")
            continue

        local_normalized = _normalize_question_list(local_question_response)
        if current_normalized == local_normalized:
            exam_name: str = config["name"]  # type: ignore[assignment]
            answer_file: Path = config["answer_file"]  # type: ignore[assignment]
            logger.info(f"当前考试题目匹配到本地模板：{exam_name}")
            return answer_file, exam_name

    return None, None


class AutoLogin(AutoLoginBase):
    def __init__(self, username, password):
        # 这里传入的是日志名称字符串，而不是 logger 对象
        super().__init__(username, password, logger.name)

    @retry_on_exception(max_retries=3, logger_name='exam')
    @authenticated_operation
    def get_exam_score(self, username):
        """
        获取考试分数
        使用装饰器自动处理认证和重试
        """
        # 从会话管理器获取会话
        session = session_manager.get_session(username)
        if not session:
            logger.error(f"无法获取用户 {username} 的会话")
            return False
            
        # 获取考试分数
        logger.debug(f"获取分数的请求头：{session.headers}")
        url = "https://lb.hnfnu.edu.cn/school/student/getKaoShi"
        response = session.get(url=url).json()
        logger.debug(f"返回的分数响应：{response}")
        exam_score = response["data"]["kaoShi"]
        if exam_score == 0:
            logger.info("考试成绩为0，提交考试数据")
            return True
        else:
            logger.info(f"存在考试分数：{exam_score}")
            # 更新考试状态为已完成，并记录分数
            completion_status.update_exam_status(username, True, exam_score)
            logger.info(f"已更新用户 {username} 的考试状态为已完成，分数：{exam_score}")
            return False

    @retry_on_exception(max_retries=3, logger_name='exam')
    @authenticated_operation
    def get_question(self):
        """
        获取题目
        使用装饰器自动处理认证和重试
        """
        # 从会话管理器获取会话
        session = session_manager.get_session(self.username)
        if not session:
            logger.error(f"无法获取用户 {self.username} 的会话")
            return None
            
        # 获取题目
        question_url = "https://lb.hnfnu.edu.cn/school/student/getTopicList"
        response = session.get(url=question_url)
        logger.debug(f"获取题目响应: {response.json()}")
        return response.json()

    #这个是将题目中的答案提取出来，如果有多套题目时更灵活。但是每届的上传的答案数据的格式不一定相同。区别于直接上传抓包的答案
    def convert_to_submission_format(self):
        data = safe_execute(
            lambda: self.get_question(),
            default_return={"data": []},
            logger_name=logger.name,
            error_handler=auth_error_handler,
            context={"username": self.username, "operation": "get_question"}
        )
        
        submission_data = {"topics": []}

        for item in data["data"]:
            topic_id = item["topicId"]
            topic_type = item["topicType"]
            # 统一答案标识为小写（适配A/B/C/D或ABCD等大小写格式）
            result = item["topicResult"].lower()
            answer = ""
            submission_item = {}

            # 1. 按题型提取并生成答案内容
            if topic_type in ["单选题", "判断题"]:
                # 提取选项对应值（如单选题result为"b"，取item["b"]的值）
                answer = item.get(result, f"未知选项（{result}）")
                # 单选题/判断题：保留answer和str双字段，值一致
                submission_item = {
                    "answer": answer,
                    "str": answer,
                    "topicId": topic_id,
                    "name": result
                }

            elif topic_type == "多选题":
                # 遍历多选题每个选项标识（如result为"abcd"，遍历a、b、c、d）
                answer_parts = []
                for char in result:
                    part = item.get(char, f"未知选项（{char}）")
                    answer_parts.append(part)
                # 多选题答案用"~"拼接，仅保留str字段（无answer字段）
                answer_str = "~".join(answer_parts)
                submission_item = {
                    "str": answer_str,
                    "topicId": topic_id,
                    "name": result
                }

            else:
                # 其他未定义题型：保留基础字段，提示未处理
                answer = f"未处理题型（{topic_type}）"
                submission_item = {
                    "answer": answer,
                    "str": answer,
                    "topicId": topic_id,
                    "name": result
                }

            submission_data["topics"].append(submission_item)

        # 转换为JSON，确保中文正常显示（如"扣篮"、"精神放松"等）
        json_submission_data = json.dumps(submission_data, ensure_ascii=False)
        logger.debug(f"转换后的数据：{json_submission_data}")
        return json_submission_data

    @retry_on_exception(max_retries=3, logger_name='exam')
    @authenticated_operation
    def submit_answer_data(self):
        """
        提交答案数据
        使用装饰器自动处理认证和重试
        """
        # 从会话管理器获取会话
        session = session_manager.get_session(self.username)
        if not session:
            logger.error(f"无法获取用户 {self.username} 的会话")
            return None
            
        # 提交答案数据
        submit_url = "https://lb.hnfnu.edu.cn/school/student/topic"
        headers = session.headers
        # 获取符合提交格式的答案
        data = self.get_answer_data()
        if not data:
            logger.warning("未获取到答案数据，本次不提交考试答案")
            return None
        # 确保请求头中包含Authorization
        headers.update(session.headers)
        # 提交答案
        session.headers.update({"Content-Type": "application/json"})
        logger.debug(f"提交答案的请求头为：{session.headers}")
        response = session.put(url=submit_url, data=data, headers=headers)

        try:
            response_json = response.json()
        except ValueError as e:
            logger.error(f"提交答案数据响应解析失败: {e}", exc_info=True)
            return None

        logger.debug(f"提交答案数据响应: {response_json}")

        # 仅在服务端明确返回成功时才认为提交成功
        if response_json.get("code") != 200:
            logger.error(f"提交考试答案失败，服务端返回: {response_json}")
            return None

        logger.info("答案提交成功")
        return response_json

    # 这里是直接用抓包得到的答案，区别于从题目中提取答案
    def get_answer_data(self):
        """
        根据当前账号获取到的题目，与本地抓包题目进行比对，自动选择对应年级的答案数据。
        如果未匹配到任何本地试卷，则返回 None。
        """
        question_data = safe_execute(
            lambda: self.get_question(),
            default_return={"data": []},
            logger_name=logger.name,
            error_handler=auth_error_handler,
            context={"username": self.username, "operation": "get_question_for_answer_match"}
        )

        answer_file_path, exam_name = match_exam_by_questions(question_data)

        if not answer_file_path:
            logger.warning("未检测到本地有该用户本次考试答案")
            return None

        logger.info(f"检测到用户 {self.username} 当前考试为：{exam_name}，使用答案文件：{answer_file_path}")

        try:
            with open(answer_file_path, "r", encoding="utf-8") as f:
                raw_content = f.read()
        except FileNotFoundError:
            logger.error(f"答案文件不存在: {answer_file_path}")
            return None
        except Exception as e:
            logger.error(f"读取答案文件失败: {answer_file_path}，错误：{e}", exc_info=True)
            return None

        # 优先尝试作为标准 JSON 使用
        try:
            json.loads(raw_content)
            return raw_content
        except json.JSONDecodeError:
            pass

        # 兼容当前使用单引号/字典字符串格式的答案文件：
        # 先用 ast.literal_eval 解析为字典，再序列化为合法 JSON 字符串
        try:
            submission_obj = ast.literal_eval(raw_content)
        except Exception as e:
            logger.error(f"答案文件内容格式不正确: {answer_file_path}，错误：{e}", exc_info=True)
            return None

        try:
            json_str = json.dumps(submission_obj, ensure_ascii=False)
            return json_str
        except Exception as e:
            logger.error(f"答案数据序列化为 JSON 失败: {answer_file_path}，错误：{e}", exc_info=True)
            return None

    def logout(self):
        # 使用会话管理器退出登录
        session_manager.logout_session(self.username)
        logger.info("退出账号")
        logger.debug("退出登录")

def just_get_answer(accounts):
    # 添加账号分隔符
    logger.info("=" * 60)
    logger.info(f"账号：{accounts[0][0]}")
    # 实例化
    username, password = accounts[0]
    auto_login = AutoLogin(username, password)
    token = auto_login.login()
    # 获取答案
    if token:
        # 解析 JSON 字符串为字典
        submission_data = json.loads(auto_login.convert_to_submission_format())

        # 遍历 topics 列表，按序号输出
        for i, topic in enumerate(submission_data["topics"], start=1):
            # 区分题型字段：单选题/判断题用answer，多选题用str
            if 'answer' in topic:
                logger.info(f"{i}.{topic['name']}:{topic['answer']}")
            else:
                logger.info(f"{i}.{topic['name']}:{topic['str']}")
    # 添加账号处理完成分隔符
    logger.info("=" * 60)

def get_put_answer(accounts):
    # 添加账号分隔符
    logger.info("=" * 60)
    logger.info(f"账号：{accounts[0][0]}")
    #实例化
    username, password = accounts[0]
    auto_login = AutoLogin(username, password)
    token = auto_login.login()
    #获取答案
    if token:
        # 解析 JSON 字符串为字典
        submission_data = json.loads(auto_login.convert_to_submission_format())
        logger.info(f"原始答案数据: {submission_data}")
    # 添加账号处理完成分隔符
    logger.info("=" * 60)


def main(accounts=None):
    # 如果没有提供账号列表，则使用过滤函数获取需要考试的用户
    if accounts is None:
        accounts = safe_execute(
            lambda: filter.get_exam_users(),
            default_return=[],
            logger_name=logger.name,
            context={"operation": "get_exam_users"}
        )
        logger.info(f"获取到 {len(accounts)} 个需要考试的用户")
    
    try:
        for account in accounts:
            # 添加账号分隔符
            logger.info("=" * 60)
            logger.info(f"账号：{account[0]}")
            
            # 使用安全执行函数处理每个账号
            safe_execute(
                lambda: process_single_account(account),
                logger_name=logger.name,
                error_handler=auth_error_handler,
                context={"username": account[0], "operation": "process_exam_account"}
            )
            
            # 添加账号处理完成分隔符
            logger.info("=" * 60)
    finally:
        # 清理所有会话
        session_manager.cleanup_all_sessions()

    logger.info("所有账号处理完成")


def process_single_account(account):
    """处理单个账号的考试"""
    # 每次循环重新实例化，确保会话重置
    username, password = account
    auto_login = AutoLogin(username, password)
    token = auto_login.login()
    
    if token:
        # 使用安全执行函数检查考试分数
        need_exam = safe_execute(
            lambda: auto_login.get_exam_score(username),
            default_return=False,
            logger_name=logger.name,
            error_handler=auth_error_handler,
            context={"username": username, "operation": "get_exam_score"}
        )

        if need_exam:
            logger.info("开始提交考试答案")
            # 使用安全执行函数提交答案
            result = safe_execute(
                lambda: auto_login.submit_answer_data(),
                logger_name=logger.name,
                error_handler=auth_error_handler,
                context={"username": username, "operation": "submit_answer"}
            )

            if result:
                logger.info("答案提交请求已成功发送，开始获取最新分数")

                # 提交成功后再次获取分数并更新考试状态
                session = session_manager.get_session(username)
                score_url = "https://lb.hnfnu.edu.cn/school/student/getKaoShi"
                score_response = safe_execute(
                    lambda: session.get(url=score_url).json(),
                    default_return={"data": {"kaoShi": 0}},
                    logger_name=logger.name,
                    error_handler=auth_error_handler,
                    context={"username": username, "operation": "get_final_score"}
                )

                exam_score = score_response["data"].get("kaoShi", 0)

                if isinstance(exam_score, (int, float)) and exam_score > 0:
                    # 仅在分数大于 0 时标记为已完成
                    safe_execute(
                        lambda: completion_status.update_exam_status(username, True, int(exam_score)),
                        logger_name=logger.name,
                        context={"username": username, "operation": "update_exam_status"}
                    )
                    logger.info(f"已更新用户 {username} 的考试状态为已完成，分数：{exam_score}")
                else:
                    logger.warning(f"提交考试答案后，分数仍为 {exam_score}，视为未完成，允许后续返工")
                    # 记录一次未完成的尝试，completed 置为 False，score 保留便于排查
                    safe_execute(
                        lambda: completion_status.update_exam_status(username, False, int(exam_score)),
                        logger_name=logger.name,
                        context={"username": username, "operation": "update_exam_status_failed"}
                    )
        else:
            logger.info("已有考试分数，跳过")
    else:
        logger.error(f"账号 {username} 登录失败")
# 测试代码
if __name__ == "__main__":
    pass
