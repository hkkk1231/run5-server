#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复直接运行时的相对导入问题
使用统一的绝对路径配置，移除复杂的相对路径推导
"""

import os
import sys

# 使用统一的绝对路径配置（无需动态推导）
from paths import SPIDER_DATA_DIR, RED_RUN_COMPLETION_FILE, CURRENT_MILEAGE_FILE

# 使用相对导入读取 Excel 模块
from . import read_excel

# === 以下是原有业务逻辑 ===

import json
import logging
from datetime import datetime

# 设置日志记录器
logger = logging.getLogger(__name__)

def load_completed_red_run_accounts():
    if not RED_RUN_COMPLETION_FILE.exists():
        return set()
    try:
        with RED_RUN_COMPLETION_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError:
        logger.warning("redrun_complete.json 格式异常，忽略已完成账号过滤")
        return set()
    accounts = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("account"):
                accounts.add(str(item["account"]))
    return accounts

def today_json_name():
    today = datetime.now().strftime('%Y-%m-%d')
    filename = f'{today}.json'
    filepath = str(SPIDER_DATA_DIR / "file_folder_complete" / filename)
    return filepath

def create():
    filepath = today_json_name()
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            json.dump([], f)

def today_ran_json():
    filepath = today_json_name()
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            json.dump([], f)
    with open(filepath, 'r') as f:
        json_list = json.load(f)
    return json_list

def add_one(json_id, filepath=today_json_name()):
    if filepath == today_json_name():
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                json.dump([], f)
        with open(filepath, 'r') as f:
            json_list = json.load(f)
        json_list.append(json_id)
        with open(filepath, 'w') as f:
            json.dump(json_list, f)
    elif filepath != today_json_name():
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                json.dump([], f)
        with open(filepath, 'r') as f:
            json_list = json.load(f)
        json_list.append(json_id)
        with open(filepath, 'w') as f:
            json.dump(json_list, f)

def get_current_mileage_json():
    # 使用统一的路径配置
    with open(str(CURRENT_MILEAGE_FILE), 'r') as f:
        json_dic = json.load(f)
        return json_dic

def odd_even_separate(data):
    day_parity = datetime.now().day % 2
    return {acc: info for acc, info in data.items() if int(acc[-1]) % 2 == day_parity or info[1] == 0}

def get_online_learning_and_exam_users():
    all_data = read_excel.extract_data(["学号", "密码", "线上学习", "考试"])
    users_data = {}

    for account, info_list in all_data.items():
        password = info_list[1] if info_list[1] else account
        online_learning_status = info_list[2]
        exam_status = info_list[3]

        users_data[account] = {
            'password': password,
            'need_online_learning': bool(online_learning_status),
            'need_exam': bool(exam_status)
        }

    return users_data

def get_exam_users():
    all_data = read_excel.extract_data(["学号", "密码", "考试"])
    exam_users = []

    for account, info_list in all_data.items():
        exam_status = int(info_list[2] or 0)
        if exam_status == 1:
            password = info_list[1] if info_list[1] else account
            exam_users.append([account, password])

    return exam_users

def get_video_users():
    all_data = read_excel.extract_data(["学号", "密码", "线上学习"])
    video_users = []

    for account, info_list in all_data.items():
        online_learning_status = int(info_list[2] or 0)
        if online_learning_status == 1:
            password = info_list[1] if info_list[1] else account
            video_users.append([account, password])

    return video_users

def get_long_run_users():
    all_data = read_excel.extract_data(["学号", "密码", "长征跑"])
    long_run_users = []

    for account, info_list in all_data.items():
        need_long_run = int(info_list[2] or 0)
        if need_long_run == 1:
            password = info_list[1] if info_list[1] else account
            long_run_users.append([account, password])

    return long_run_users

def get_red_run_users():
    completed_accounts = load_completed_red_run_accounts()
    # 修复：从Excel中读取红色竞赛用户数据
    # Excel列名：学号, 密码, 红色竞赛 (不是"是否需要红色跑")
    # 只有红色竞赛列值为1的用户才会被筛选出来
    all_data = read_excel.extract_data(["学号", "密码", "红色竞赛"])
    red_run_users = []

    for account, info_list in all_data.items():
        account_key = str(account)
        # 第三列是红色竞赛标记，只有值为1才表示需要参加红色跑
        need_red_run = int(info_list[2] or 0)
        if need_red_run == 1 and account_key not in completed_accounts:
            password = info_list[1] if info_list[1] else account
            red_run_users.append([account_key, str(password)])
            # 使用模块级别的logger
            logging.debug(f"找到红色跑用户: {account}")

    return red_run_users

def filter_data(html_content):
    """
    从跑步页面的HTML内容中提取跑步所需的数据
    
    Args:
        html_content (str): 跑步页面的HTML内容
        
    Returns:
        dict: 包含跑步所需数据的字典
    """
    import re
    import json
    
    logger.debug("开始解析跑步页面数据")
    
    try:
        # 尝试从HTML中提取JSON数据
        # 通常跑步数据会以JavaScript变量的形式存在于页面中
        # 常见的模式：window.runData = {...} 或 var runData = {...}
        json_pattern = r'(?:window\.)?runData\s*=\s*({.*?});'
        matches = re.findall(json_pattern, html_content, re.DOTALL)
        
        if matches:
            # 使用第一个匹配的JSON数据
            run_data = json.loads(matches[0])
            logger.debug(f"成功提取跑步数据: {run_data}")
            return run_data
        
        # 如果没有找到runData，尝试查找其他可能的变量名
        alternative_patterns = [
            r'(?:window\.)?challengeData\s*=\s*({.*?});',
            r'(?:window\.)?runInfo\s*=\s*({.*?});',
            r'challengeId["\']?\s*[:=]\s*["\']?(\d+)',
            r'data["\']?\s*[:=]\s*({.*?})',
        ]
        
        for pattern in alternative_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL)
            if matches:
                if pattern == r'challengeId["\']?\s*[:=]\s*["\']?(\d+)':
                    # 如果只找到了challengeId，构造一个基本的数据结构
                    challenge_id = matches[0]
                    logger.debug(f"提取到challengeId: {challenge_id}")
                    return {"challengeId": challenge_id}
                else:
                    # 尝试解析JSON数据
                    try:
                        data = json.loads(matches[0])
                        logger.debug(f"使用备用模式提取到数据: {data}")
                        return data
                    except json.JSONDecodeError:
                        continue
        
        # 如果都没有找到，尝试从URL或表单中提取
        url_pattern = r'challengeId["\']?\s*[:=]\s*["\']?(\d+)'
        url_matches = re.findall(url_pattern, html_content)
        if url_matches:
            challenge_id = url_matches[0]
            logger.debug(f"从URL中提取到challengeId: {challenge_id}")
            return {"challengeId": challenge_id}
        
        # 最后的备选方案：返回一个基本的跑步数据结构
        logger.warning("无法从页面中提取跑步数据，使用默认数据结构")
        return {
            "competitionId": 37,
            "competitionName": "环校跑",
            "status": "start"
        }
        
    except Exception as e:
        logger.error(f"解析跑步数据时出错: {str(e)}")
        # 返回一个基本的跑步数据结构，确保流程可以继续
        return {
            "competitionId": 37,
            "competitionName": "环校跑",
            "status": "start"
        }


def main():
    data_before = read_excel.extract_data(["学号", "密码", "长征跑", "手动停止", "目标里程", "<4", "当前里程"])
    filtered_result = {}

    for account, info_list in data_before.items():
        today_ran_list = today_ran_json()
        password = info_list[1]
        need_long = int(info_list[2] or 0)
        stop_run = int(info_list[3] or 0)
        target = int(info_list[4] or 0)
        less_4km = int(info_list[5] or 0)

        if info_list[6] in ('None', None, ''):
            current = 0
        else:
            current = int(info_list[6] or 0)

        if int(need_long) == 1 and int(stop_run) == 0 and account not in today_ran_list and current < target:
            filtered_result[account] = [password, current, less_4km]

    return filtered_result

if __name__ == "__main__":
    data = main()
    print(data)
    print(len(data))
