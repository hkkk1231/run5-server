import os
import sys
from pathlib import Path

# 统一使用 main_code 作为导入根目录，兼容直接运行和 -m 方式
CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[2]  # .../main_code
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

# 使用统一的绝对路径配置
from paths import VIDEO_EXAM_LOG

# 统一导入：所有模块都使用绝对导入（以 spider 为顶级包）
from spider.package.data import filter
from spider.study_online import video_spider, exam_spider, completion_status
from spider.package.core.common_utils import setup_logger

# 设置日志
logger = setup_logger("video_exam", str(VIDEO_EXAM_LOG))


def video_and_exam():
    """根据Excel中的线上学习和考试状态执行相应任务，并管理完成状态"""
    logger.info("开始视频观看和考试脚本")

    # 获取需要线上学习和考试的用户数据
    users_data = filter.get_online_learning_and_exam_users()
    #users_data = {'24407010326': {'password': '24407010326', 'need_online_learning': False, 'need_exam': True}}

    # 根据完成状态过滤用户
    filtered_users = completion_status.filter_users_by_status(users_data)

    if not filtered_users:
        logger.info("没有需要处理的用户")
        return

    logger.info(f"共 {len(filtered_users)} 个用户需要处理")

    for username, user_info in filtered_users.items():
        password = user_info['password']
        account = [username, password]

        logger.info(f"处理账号: {username}")

        # 处理线上学习
        if user_info['need_online_learning'] and not completion_status.is_study_completed(username):
            logger.info(f"开始视频观看: {username}")
            try:
                video_results = video_spider.main([account])
                video_success = bool(video_results.get(username))
                completion_status.update_study_status(username, video_success)
                if video_success:
                    logger.info(f"学习任务完成: {username}")
                else:
                    logger.warning(f"学习任务未完成: {username}")
            except Exception as e:
                # 控制台只显示简短信息
                logger.warning(f"学习任务失败: {username}")
                # 详细异常信息只记录到文件
                logger.debug(f"学习任务异常详情: {str(e)}", exc_info=True)
                # 更新学习状态为未完成
                completion_status.update_study_status(username, False)
        elif user_info['need_online_learning']:
            logger.info(f"学习任务已完成: {username}")
        else:
            logger.debug(f"不需要线上学习: {username}")

        # 处理考试
        if user_info['need_exam']:
            logger.info(f"开始考试: {username}")
            try:
                exam_spider.main([account])
                # 注意：不需要在这里更新考试状态，因为exam_spider.main已经更新了
                logger.info(f"考试任务完成: {username}")
            except Exception as e:
                # 控制台只显示简短信息
                logger.warning(f"考试任务失败: {username}")
                # 详细异常信息只记录到文件
                logger.debug(f"考试任务异常详情: {str(e)}", exc_info=True)
                # 更新考试状态为未完成
                completion_status.update_exam_status(username, False)

    logger.info("所有任务完成")


if __name__ == '__main__':
    video_and_exam()
