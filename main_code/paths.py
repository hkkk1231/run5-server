#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
项目路径统一配置 - pathlib 版本
所有路径统一使用绝对路径，基于 pathlib 实现，现代化且清晰
"""

from pathlib import Path

# ==============================================================================
# 项目根目录 - 使用当前文件位置自动推导
# ==============================================================================
# 当前文件的绝对路径
_CURRENT_FILE = Path(__file__).resolve()
# 项目根目录：/root/desktop/run5-server
PROJECT_ROOT = _CURRENT_FILE.parent.parent
# main_code 目录
MAIN_CODE_DIR = _CURRENT_FILE.parent

# ==============================================================================
# Spider 目录结构
# ==============================================================================
SPIDER_DIR = PROJECT_ROOT / "main_code" / "spider"
SPIDER_PACKAGE_DIR = SPIDER_DIR / "package"
SPIDER_RESOURCE_DIR = SPIDER_DIR / "resource"
SPIDER_DATA_DIR = SPIDER_RESOURCE_DIR / "data"
SPIDER_CONFIG_DIR = SPIDER_RESOURCE_DIR / "config"
SPIDER_LOGS_DIR = SPIDER_RESOURCE_DIR / "logs"

# ==============================================================================
# 子模块目录
# ==============================================================================
STUDY_ONLINE_DIR = SPIDER_DIR / "study_online"
LONG_RUN_DIR = SPIDER_DIR / "long_run"
RED_RUN_DIR = SPIDER_DIR / "red_run"

# Package 子目录
PACKAGE_CORE_DIR = SPIDER_PACKAGE_DIR / "core"
PACKAGE_AUTH_DIR = SPIDER_PACKAGE_DIR / "auth"
PACKAGE_DATA_DIR = SPIDER_PACKAGE_DIR / "data"
PACKAGE_NETWORK_DIR = SPIDER_PACKAGE_DIR / "network"

# ==============================================================================
# 资源文件路径
# ==============================================================================

# JSON 数据文件
ERROR_ACCOUNTS_FILE = SPIDER_DATA_DIR / "error_accounts.json"
STUDY_STATUS_FILE = SPIDER_DATA_DIR / "study_status.json"
EXAM_STATUS_FILE = SPIDER_DATA_DIR / "exam_status.json"
CURRENT_MILEAGE_FILE = SPIDER_DATA_DIR / "current_mileage.json"
ACCOUNT_NAME_FILE = SPIDER_DATA_DIR / "account_name.json"
RED_RUN_COMPLETION_FILE = SPIDER_DATA_DIR / "redrun_complete.json"
RED_RUN_ERROR_PASSWORD_FILE = SPIDER_DATA_DIR / "red_error_password.json"

# 配置文件
USER_AGENT_FILE = SPIDER_CONFIG_DIR / "user_agent.json"

# Excel 文件
EXCEL_FILE = SPIDER_DATA_DIR / "2025.9.1_for_computer.xlsx"

# ==============================================================================
# 日志文件路径
# ==============================================================================
VIDEO_LOG = SPIDER_LOGS_DIR / "video_log.txt"
EXAM_LOG = SPIDER_LOGS_DIR / "exam_log.txt"
COMPLETION_STATUS_LOG = SPIDER_LOGS_DIR / "completion_status_log.txt"
VIDEO_EXAM_LOG = SPIDER_LOGS_DIR / "video_exam_log.txt"
RED_RUN_LOG_FILE = SPIDER_LOGS_DIR / "redrun_log.txt"

# ==============================================================================
# 便捷函数 - 转换 Path 对象为字符串（兼容性）
# ==============================================================================
def to_str(path: Path) -> str:
    """将 Path 对象转换为字符串，保持向后兼容"""
    return str(path)

def ensure_dir(path: Path) -> Path:
    """确保目录存在"""
    path.mkdir(parents=True, exist_ok=True)
    return path

# ==============================================================================
# 使用说明
# ==============================================================================
# 推荐用法：
#   from paths import SPIDER_DATA_DIR
#   from paths import ERROR_ACCOUNTS_FILE
#
# 或导入整个模块：
#   from paths import *
#
# 获取字符串路径（向后兼容）：
#   log_file = str(VIDEO_LOG)
#   data_dir = str(SPIDER_DATA_DIR)
#
# 确保目录存在：
#   from paths import ensure_dir
#   ensure_dir(SPIDER_LOGS_DIR)
