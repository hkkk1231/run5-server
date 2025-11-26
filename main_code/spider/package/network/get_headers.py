import json
import random
import os

# 使用统一的绝对路径配置
from paths import USER_AGENT_FILE


def get_headers():
    # 提取UA池
    file_path = str(USER_AGENT_FILE)

    # 如果文件不存在，记录错误并使用默认值
    if not os.path.exists(file_path):
        print("警告: 无法找到user_agent.json文件，使用默认User-Agent")
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            user_agent_json = json.load(f)
            user_agent = random.choice(user_agent_json)
    
    #设置get请求头和post请求头
    get_headers = {
        "Authorization": "",
        "user-agent": user_agent,
        "Host": "lb.hnfnu.edu.cn",
        "Connection": "Keep-Alive",
        "Accept-Encoding": "gzip"
    }

    return get_headers

if __name__ == '__main__':
    print(f"当前目录：{os.getcwd()}")
    print(get_headers())
