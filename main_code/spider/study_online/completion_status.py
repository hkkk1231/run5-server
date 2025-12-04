#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
完成状态管理模块
负责读取和更新学习与考试状态文件
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

# 统一使用 main_code 作为导入根目录，兼容直接运行和 -m 方式
CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[2]  # .../main_code
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

# 使用统一的绝对路径配置
from paths import STUDY_STATUS_FILE, EXAM_STATUS_FILE, COMPLETION_STATUS_LOG

# 统一导入：所有模块都使用绝对导入
from spider.package.core.common_utils import setup_logger

# 设置日志
logger = setup_logger("completion_status", str(COMPLETION_STATUS_LOG))


def load_status(status_file: str) -> Dict[str, Any]:
    """
    加载状态文件
    
    Args:
        status_file: 状态文件路径
        
    Returns:
        状态字典
    """
    try:
        if os.path.exists(status_file):
            with open(status_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        # 控制台只显示简短信息
        logger.warning("加载状态文件失败")
        # 详细异常信息只记录到文件
        logger.debug(f"加载状态文件失败详情: {str(e)}", exc_info=True)
        return {}


def save_status(status_file: str, status_data: Dict[str, Any]) -> bool:
    """
    保存状态文件
    
    Args:
        status_file: 状态文件路径
        status_data: 要保存的状态数据
        
    Returns:
        是否保存成功
    """
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(status_file), exist_ok=True)
        
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"保存状态文件失败: {e}")
        return False


def get_study_status() -> Dict[str, Any]:
    """
    获取学习状态

    Returns:
        学习状态字典
    """
    return load_status(str(STUDY_STATUS_FILE))


def get_exam_status() -> Dict[str, Any]:
    """
    获取考试状态

    Returns:
        考试状态字典
    """
    return load_status(str(EXAM_STATUS_FILE))


def update_study_status(username: str, completed: bool = True) -> bool:
    """
    更新学习状态

    Args:
        username: 用户名
        completed: 是否完成

    Returns:
        是否更新成功
    """
    status_data = get_study_status()
    status_data[username] = {
        "completed": completed,
        "date": datetime.now().strftime("%Y-%m-%d-%H-%M")
    }
    return save_status(str(STUDY_STATUS_FILE), status_data)


def update_exam_status(username: str, completed: bool = True, score: int = None) -> bool:
    """
    更新考试状态

    Args:
        username: 用户名
        completed: 是否完成
        score: 考试分数（可选）

    Returns:
        是否更新成功
    """
    status_data = get_exam_status()
    user_status = status_data.get(username, {})

    # 保留原有的completed和date字段
    user_status["completed"] = completed
    user_status["date"] = datetime.now().strftime("%Y-%m-%d-%H-%M")

    # 如果提供了分数，则添加或更新分数字段
    if score is not None:
        user_status["score"] = score

    status_data[username] = user_status
    return save_status(str(EXAM_STATUS_FILE), status_data)


def is_study_completed(username: str) -> bool:
    """
    检查学习是否完成
    
    Args:
        username: 用户名
        
    Returns:
        是否已完成学习
    """
    status_data = get_study_status()
    user_status = status_data.get(username, {})
    
    # 检查completed字段
    if "completed" in user_status:
        return user_status["completed"]
    
    # 兼容旧格式：如果有date字段但没有completed字段，认为已完成
    if "date" in user_status and "completed" not in user_status:
        return True
    
    return False


def is_exam_completed(username: str) -> bool:
    """
    检查考试是否完成
    
    Args:
        username: 用户名
        
    Returns:
        是否已完成考试
    """
    status_data = get_exam_status()
    user_status = status_data.get(username, {})

    completed = user_status.get("completed")
    score = user_status.get("score")

    # 如果显式记录了 completed，优先按 completed 判断
    if completed is not None:
        # 逻辑修正：如果标记为已完成但分数为 0，则视为未完成，允许后续返工
        if completed and isinstance(score, (int, float)) and score <= 0:
            return False
        return bool(completed)

    # 兼容旧格式：如果有 date 字段但没有 completed 字段，认为已完成
    if "date" in user_status and "completed" not in user_status:
        return True

    return False


def filter_users_by_status(users_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    根据状态过滤用户
    
    Args:
        users_data: 从filter.get_online_learning_and_exam_users()获取的用户数据
        
    Returns:
        过滤后的用户数据
    """
    filtered_users = {}
    
    for username, user_info in users_data.items():
        # 检查学习状态
        need_study = user_info.get('need_online_learning', False)
        study_completed = is_study_completed(username)
        
        # 检查考试状态
        need_exam = user_info.get('need_exam', False)
        exam_completed = is_exam_completed(username)
        
        # 如果需要学习但未完成，或需要考试但未完成，则保留该用户
        if (need_study and not study_completed) or (need_exam and not exam_completed):
            filtered_users[username] = user_info
    
    return filtered_users


if __name__ == '__main__':
    # 测试代码
    logger.info("学习状态: %s", get_study_status())
    logger.info("考试状态: %s", get_exam_status())
    
    # 测试更新状态
    update_study_status("test_user", True)
    update_exam_status("test_user", True)
    
    logger.info("更新后状态: %s", get_study_status())
