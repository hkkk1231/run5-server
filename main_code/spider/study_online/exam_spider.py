import requests
import json
import os
import sys
import logging

# 统一使用绝对导入，基于项目根目录的现代pathlib方式
# 项目根目录：run5-server
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 使用统一的绝对路径配置
from paths import EXAM_LOG, SPIDER_DATA_DIR

# 统一导入：所有模块都使用绝对导入
from main_code.spider.package.network.get_headers import get_headers
from main_code.spider.package.data import filter
from main_code.spider.study_online import completion_status
from main_code.spider.package.auth.login import create_authenticated_session
from main_code.spider.package.auth.session_manager import session_manager
from main_code.spider.package.core.common_utils import AutoLoginBase, authenticated_operation, setup_logger
from main_code.spider.package.core.error_handler import retry_on_exception, safe_execute, auth_error_handler

# 设置日志
logger = setup_logger('exam', str(EXAM_LOG))


class AutoLogin(AutoLoginBase):
    def __init__(self, username, password):
        super().__init__(username, password, logger)

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
            logger=logger,
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
        # 确保请求头中包含Authorization
        headers.update(session.headers)
        # 提交答案
        session.headers.update({"Content-Type": "application/json"})
        logger.debug(f"提交答案的请求头为：{session.headers}")
        response = session.put(url=submit_url, data=data, headers=headers)
        logger.debug(f"提交答案数据响应: {response.json()}")
        logger.info("答案提交成功")
        return response.json()

    # 这里是直接用抓包得到的答案，区别于从题目中提取答案
    def get_answer_data(self):
        # 使用绝对路径获取答案文件路径
        answer_file_path = str(SPIDER_DATA_DIR / "立正.txt")

        with open(answer_file_path, "r", encoding="utf-8") as f:
            put_answer = f.read()
        return put_answer

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
            logger=logger,
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
                logger=logger,
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
            logger=logger,
            error_handler=auth_error_handler,
            context={"username": username, "operation": "get_exam_score"}
        )
        
        if need_exam:
            logger.info("开始提交考试答案")
            # 使用安全执行函数提交答案
            result = safe_execute(
                lambda: auto_login.submit_answer_data(),
                logger=logger,
                error_handler=auth_error_handler,
                context={"username": username, "operation": "submit_answer"}
            )
            
            if result:
                logger.info(f"答案提交成功")
                
                # 提交成功后再次获取分数并更新考试状态
                session = session_manager.get_session(username)
                score_url = "https://lb.hnfnu.edu.cn/school/student/getKaoShi"
                score_response = safe_execute(
                    lambda: session.get(url=score_url).json(),
                    default_return={"data": {"kaoShi": 0}},
                    logger=logger,
                    error_handler=auth_error_handler,
                    context={"username": username, "operation": "get_final_score"}
                )
                
                exam_score = score_response["data"]["kaoShi"]
                
                # 更新考试状态和分数
                safe_execute(
                    lambda: completion_status.update_exam_status(username, True, exam_score),
                    logger=logger,
                    context={"username": username, "operation": "update_exam_status"}
                )
                logger.info(f"已更新用户 {username} 的考试状态为已完成，分数：{exam_score}")
        else:
            logger.info("已有考试分数，跳过")
    else:
        logger.error(f"账号 {username} 登录失败")
# 测试代码
if __name__ == "__main__":
    pass