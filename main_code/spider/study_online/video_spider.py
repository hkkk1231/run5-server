import requests
import os
import sys
import logging
from pathlib import Path

# 统一使用 main_code 作为导入根目录，兼容直接运行和 -m 方式
CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[2]  # .../main_code
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

# 使用统一的绝对路径配置
from paths import VIDEO_LOG

# 统一导入：所有模块都使用绝对导入（以 spider 为顶级包）
from spider.package.network.get_headers import get_headers
from spider.package.data import filter
from spider.package.auth.login import create_authenticated_session
from spider.package.auth.session_manager import session_manager
from spider.package.core.common_utils import AutoLoginBase, authenticated_operation, setup_logger
from spider.package.core.error_handler import retry_on_exception, safe_execute, auth_error_handler

# 设置日志
logger = setup_logger('video', str(VIDEO_LOG))




class AutoLogin(AutoLoginBase):
    def __init__(self, username, password):
        super().__init__(username, password, logger)

    @retry_on_exception(max_retries=3, logger_name='video')
    @authenticated_operation
    def get_chapter_list(self):
        """
        获取章节列表
        使用装饰器自动处理认证和重试
        """
        # 从会话管理器获取会话
        session = session_manager.get_session(self.username)
        if not session:
            logger.error(f"无法获取用户 {self.username} 的会话")
            return None
            
        # 获取章节列表
        chapter_list_url = "https://lb.hnfnu.edu.cn/school/student/getChapterList"
        # 确保请求头中包含Authorization
        response = session.get(url=chapter_list_url)
        logger.debug(f"获取章节列表响应: {response.json()}")
        return response.json()

    @retry_on_exception(max_retries=3, logger_name='video')
    @authenticated_operation
    def submit_video_data(self, student_number):
        """
        提交视频数据
        使用装饰器自动处理认证和重试
        """
        # 从会话管理器获取会话
        session = session_manager.get_session(self.username)
        if not session:
            logger.error(f"无法获取用户 {self.username} 的会话")
            return None
            
        # 提交视频数据
        submit_url = "https://lb.hnfnu.edu.cn/school/student/DaTiOver"
        data = {
            "studentNumber": student_number,
            "videoGrade": 20
        }
        response = session.post(url=submit_url, json=data)
        return response.json()

    @retry_on_exception(max_retries=3, logger_name='video')
    @authenticated_operation
    def submit_status(self, student_number, file_id):
        """
        提交状态
        使用装饰器自动处理认证和重试
        """
        # 从会话管理器获取会话
        session = session_manager.get_session(self.username)
        if not session:
            logger.error(f"无法获取用户 {self.username} 的会话")
            return None
            
        # 提交状态
        submit_url = "https://lb.hnfnu.edu.cn/school/student/addStatus"
        data = {
            "fileId": file_id,
            "studentNumber": student_number
        }
        response = session.post(url=submit_url, json=data)
        logger.debug(f"提交状态响应: {response.json()}")
        return response.json()

    def process_videos(self, student_number):
        """
        处理视频学习流程
        
        Args:
            student_number: 学号
            
        Returns:
            bool: 所有视频是否都已处理完成
        """
        # 使用安全执行函数获取章节列表
        chapter_list = safe_execute(
            lambda: self.get_chapter_list(),
            default_return={"data": []},
            logger=logger,
            error_handler=auth_error_handler,
            context={"username": self.username, "operation": "get_chapter_list"}
        )
        
        if not chapter_list or "data" not in chapter_list:
            logger.error(f"无法获取章节列表，跳过用户 {self.username}")
            return False
            
        all_videos_completed = True  # 初始化一个标志变量，假设所有视频都已完成
        processed_videos = 0  # 记录处理的视频数量

        for chapter in chapter_list["data"]:
            for file_info in chapter["scChapterFileList"]:
                video_name = chapter["chapterName"]
                logger.debug(f"file_info: {file_info}")
                if file_info["state"] != "1":
                    file_id = file_info["fileId"]  # 获取视频名称，如果没有则为 None
                    logger.info(f"处理视频：{video_name}")
                    logger.debug(f"处理视频: fileId={file_id}, videoName={video_name}")
                    
                    # 使用安全执行函数提交状态
                    safe_execute(
                        lambda: self.submit_status(student_number, file_id),
                        logger=logger,
                        error_handler=auth_error_handler,
                        context={"username": self.username, "operation": "submit_status"}
                    )
                    
                    # 使用安全执行函数提交视频数据
                    safe_execute(
                        lambda: self.submit_video_data(student_number),
                        logger=logger,
                        error_handler=auth_error_handler,
                        context={"username": self.username, "operation": "submit_video_data"}
                    )
                    
                    all_videos_completed = False  # 有视频需要处理，说明不是全部完成
                    processed_videos += 1  # 增加处理计数

                else:
                    logger.debug(f"视频已完成：{video_name}")

        # 根据标志变量的值决定返回结果
        if all_videos_completed:
            logger.debug(f"学号 {student_number} 的学习任务已完成")
            return True
        else:
            logger.info(f"学号 {student_number} 处理了 {processed_videos} 个视频")
            return False

    def logout(self):
        # 使用会话管理器退出登录
        session_manager.logout_session(self.username)
        logger.debug(f"用户 {self.username} 已退出登录")
        logger.debug("退出登录")

def main(accounts=None):
    # 如果没有提供账号列表，则使用过滤函数获取需要视频学习的用户
    if accounts is None:
        accounts = safe_execute(
            lambda: filter.get_video_users(),
            default_return=[],
            logger=logger,
            context={"operation": "get_video_users"}
        )
        logger.info(f"获取到 {len(accounts)} 个需要视频学习的用户")
    
    for account in accounts:
        username, password = account
        # 添加账号分隔符
        logger.info("=" * 60)
        logger.info(f"账号：{username}")
        
        # 使用安全执行函数处理每个账号
        safe_execute(
            lambda: process_single_account(username, password),
            logger=logger,
            error_handler=auth_error_handler,
            context={"username": username, "operation": "process_account"}
        )
        
        # 添加账号处理完成分隔符
        logger.info("=" * 60)
        
    logger.info("所有账号处理完成")
    # 清理所有会话
    session_manager.cleanup_all_sessions()


def process_single_account(username, password):
    """处理单个账号的视频学习"""
    auto_login = AutoLogin(username, password)
    token = auto_login.login()
    if token:
        if auto_login.process_videos(username):
            logger.info("视频观看完成")
        else:
            logger.info("视频已全部观看")
    auto_login.logout()

# 测试代码
if __name__ == "__main__":
    #accounts = vedio_exam.extract_excel()
    accounts = [["24418080145", "24418080145"]]
    main(accounts)
