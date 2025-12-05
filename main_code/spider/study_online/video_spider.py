import sys
from pathlib import Path

# 统一使用 main_code 作为导入根目录，兼容直接运行和 -m 方式
CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[2]  # .../main_code
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

# 使用统一的绝对路径配置
from paths import VIDEO_LOG

# 统一导入：所有模块都使用绝对导入（以 spider 为顶级包）
from spider.package.data import filter
from spider.package.auth.session_manager import session_manager
from spider.package.core.common_utils import AutoLoginBase, authenticated_operation, setup_logger
from spider.package.core.error_handler import retry_on_exception, safe_execute, auth_error_handler

# 设置日志
logger = setup_logger('video', str(VIDEO_LOG))


class AutoLogin(AutoLoginBase):
    def __init__(self, username, password):
        # 传递日志名称字符串给基类，避免 getLogger 收到 logger 对象
        super().__init__(username, password, logger.name)

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
            logger_name=logger.name,
            error_handler=auth_error_handler,
            context={"username": self.username, "operation": "get_chapter_list"}
        )
        
        if not chapter_list or "data" not in chapter_list:
            logger.error(f"无法获取章节列表，跳过用户 {self.username}")
            return False
            
        processed_videos = 0  # 记录处理的视频数量
        pending_files = []

        for chapter in chapter_list.get("data", []):
            files = chapter.get("scChapterFileList") or []
            video_name = chapter.get("chapterName", "")
            for file_info in files:
                logger.debug(f"file_info: {file_info}")
                if file_info.get("state") != "1":
                    pending_files.append((video_name, file_info))

        if not pending_files:
            logger.debug(f"学号 {student_number} 的学习任务已完成")
            return True

        for video_name, file_info in pending_files:
            file_id = file_info.get("fileId")
            if not file_id:
                logger.warning(f"视频 {video_name} 缺少 fileId，跳过")
                continue

            logger.info(f"处理视频：{video_name}")
            logger.debug(f"处理视频: fileId={file_id}, videoName={video_name}")
            
            # 使用安全执行函数提交状态
            safe_execute(
                lambda fid=file_id: self.submit_status(student_number, fid),
                logger_name=logger.name,
                error_handler=auth_error_handler,
                context={"username": self.username, "operation": "submit_status"}
            )
            
            # 使用安全执行函数提交视频数据
            safe_execute(
                lambda: self.submit_video_data(student_number),
                logger_name=logger.name,
                error_handler=auth_error_handler,
                context={"username": self.username, "operation": "submit_video_data"}
            )
            processed_videos += 1

        logger.info(f"学号 {student_number} 已尝试处理 {processed_videos} 个视频，开始校验结果")
        refreshed_list = safe_execute(
            lambda: self.get_chapter_list(),
            default_return={"data": []},
            logger_name=logger.name,
            error_handler=auth_error_handler,
            context={"username": self.username, "operation": "refresh_chapter_list"}
        )

        if not refreshed_list or "data" not in refreshed_list:
            logger.warning(f"无法在处理后确认学习结果，学号 {student_number} 视为未完成")
            return False

        remaining = [
            file_info
            for chapter in refreshed_list.get("data", [])
            for file_info in (chapter.get("scChapterFileList") or [])
            if file_info.get("state") != "1"
        ]

        if remaining:
            logger.warning(f"学号 {student_number} 仍有 {len(remaining)} 个视频未完成")
            return False

        logger.info(f"学号 {student_number} 视频任务已全部完成")
        return True

    def logout(self):
        # 使用会话管理器退出登录
        session_manager.logout_session(self.username)
        logger.debug(f"用户 {self.username} 已退出登录")
        logger.debug("退出登录")

def main(accounts=None):
    """启动视频学习任务，返回每个账号的完成状态。"""
    results = {}

    # 如果没有提供账号列表，则使用过滤函数获取需要视频学习的用户
    if accounts is None:
        accounts = safe_execute(
            lambda: filter.get_video_users(),
            default_return=[],
            logger_name=logger.name,
            context={"operation": "get_video_users"}
        )
        logger.info(f"获取到 {len(accounts)} 个需要视频学习的用户")
    
    try:
        for account in accounts:
            username, password = account
            # 添加账号分隔符
            logger.info("=" * 60)
            logger.info(f"账号：{username}")
            
            # 使用安全执行函数处理每个账号
            result = safe_execute(
                lambda u=username, p=password: process_single_account(u, p),
                default_return=False,
                logger_name=logger.name,
                error_handler=auth_error_handler,
                context={"username": username, "operation": "process_account"}
            )
            results[username] = bool(result)
            
            # 添加账号处理完成分隔符
            logger.info("=" * 60)
    finally:
        logger.info("所有账号处理完成")
        # 清理所有会话
        session_manager.cleanup_all_sessions()

    return results


def process_single_account(username, password):
    """处理单个账号的视频学习"""
    auto_login = AutoLogin(username, password)
    token = auto_login.login()
    if not token:
        logger.warning(f"{username} 登录失败，跳过视频任务")
        auto_login.logout()
        return False

    try:
        completed = auto_login.process_videos(username)
        if completed:
            logger.info("视频观看任务确认完成")
        else:
            logger.warning("视频学习未全部完成，将在下次重试")
        return completed
    finally:
        auto_login.logout()


# 测试代码
if __name__ == "__main__":
    main()
