#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复直接运行时的相对导入问题
使用统一的绝对路径配置，移除复杂的相对路径推导
"""

import os
import sys

# 使用统一的绝对路径配置（无需动态推导）
from paths import SPIDER_DATA_DIR

# 使用相对导入读取 Excel 模块
from . import read_excel

# === 以下是原有业务逻辑 ===

import json
import logging
from datetime import datetime

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
    all_data = read_excel.extract_data(["学号", "密码", "是否需要红色跑"])
    red_run_users = []

    for account, info_list in all_data.items():
        need_red_run = int(info_list[2] or 0)
        if need_red_run == 1:
            password = info_list[1] if info_list[1] else account
            red_run_users.append([account, password])

    return red_run_users

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
