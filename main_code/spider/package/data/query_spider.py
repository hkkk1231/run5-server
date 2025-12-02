import requests
import logging
import json
import time
import os
from pathlib import Path

# 兼容性处理：支持直接运行和模块导入
if __name__ == "__main__":
    import sys
    current_file = Path(__file__).resolve()
    main_code_dir = current_file.parents[3]  # .../main_code
    if str(main_code_dir) not in sys.path:
        sys.path.insert(0, str(main_code_dir))
    from spider.package.network.get_headers import get_headers
    from spider.package.data.read_excel import extract_data
    from spider.package.auth.login import create_authenticated_session, get_error_accounts
    from spider.package.auth.session_manager import session_manager
else:
    from ..network.get_headers import get_headers
    from .read_excel import extract_data
    from ..auth.login import create_authenticated_session, get_error_accounts
    from ..auth.session_manager import session_manager

# 使用统一的绝对路径配置
from paths import ACCOUNT_NAME_FILE, CURRENT_MILEAGE_FILE


class Query:
    def __init__(self, username, password):
        # 使用统一的会话管理器创建认证会话
        self.username = username
        self.password = password
        self.headers = get_headers()
        self.session = create_authenticated_session(username, password, headers=self.headers)
        self.result_query = []
        
        if not self.session:
            raise ValueError(f"无法为用户 {username} 创建认证会话")
        
        # 将会话存储到会话管理器中
        session_manager._active_sessions[username] = self.session
        session_manager._session_tokens[username] = self.session.headers.get("Authorization", "").replace("Bearer ", "")
        session_manager._session_last_used[username] = time.time()

    def write_json(self, data, file):
        # 将当前字典写入json文件
        with open(file, 'w', encoding='utf-8') as f:  # 在这里指定文件编码
            # 转换为账号为键，指定值为值的字典
            json.dump(data, f, ensure_ascii=False, indent=4)
            #print(f"写入成功：{data}")

    def get_json(self, file):
        #将当前字典从json文件取出
        with open(file, 'r') as f:
            json_dic = json.load(f)
            #print("获取成功")
            return json_dic

    def update_json(self, account, value, file):
        """更新配置文件"""
        #读取的json文件
        json_mileage_dict = self.get_json(file)
        #account在字典的键中，就更新{account: value}。如果不在就增加相应的键值对
        json_mileage_dict.update({account: value})
        #写入json文件中
        self.write_json(json_mileage_dict, file)
        #logging.info(f"已更新数据:{json_mileage_dict}")

    def login(self, username, inner_password):
        # 由于在__init__中已经通过create_authenticated_session完成了登录，这里只需验证会话是否有效
        if self.session:
            return True
        else:
            self.result_query.append([username, "密码错误登录失败"])
            print("跳过并记录")
            return False

    def query_record(self, account, token=None):
        """查询账号跑步记录，token 为可选覆盖值"""
        if isinstance(token, str) and token:
            bearer_token = token if token.startswith("Bearer ") else f"Bearer {token}"
            self.session.headers.update({"Authorization": bearer_token})
        # 请求记录页面url
        mileage_url = "https://lb.hnfnu.edu.cn/school/student/getMyLongMarchList"
        respond_json = self.session.get(mileage_url, headers=self.session.headers).json()

        # 检查响应是否包含rows字段
        if not respond_json.get('rows'):
            logging.warning(f"账号 {account} 查询记录失败，API响应: {respond_json}")
            # 如果没有rows字段，返回0表示没有记录
            return 0

        # 如果有响应就获取并更新名字
        if respond_json['rows']:
            name = respond_json['rows'][0]['studentName']
            logging.info(f"姓名：{name}")
            self.update_json(account, name, str(ACCOUNT_NAME_FILE))

        # 获取记录数据
        mileages = [item["mileage"] for item in respond_json["rows"]]
        mileages_sum = sum(mileages)
        logging.info(f"当前里程：{round(mileages_sum, 2)}")
        # 更新里程
        self.update_json(account, mileages_sum, str(CURRENT_MILEAGE_FILE))
        if not respond_json["rows"]:
            return 0
        else:
            return mileages_sum

    def logout(self):
        # 使用会话管理器退出登录
        session_manager.logout_session(self.username)

    def main(self, account_password_dic):
        try:
            for account, attribute_list in account_password_dic.items():
                try:
                    print("==================================")
                    password = attribute_list[0]
                    print(f"学号：{account}，密码：{password}")
                    
                    # 使用统一的会话管理器，为每个账号创建Query实例
                    query = Query(account, password)
                    
                    # 发送登录请求，并返回响应数据
                    login_token = query.login(account, password)
                    #case切换模式，正确登录时token的布尔值为True
                    if login_token:
                        #返回里程并存入列表
                        mileage = query.query_record(account, login_token)
                        self.result_query.append([account, password, round(mileage, 2)])
                    #退出登录
                    query.logout()
                except Exception as e:
                    # 控制台只显示简短信息
                    logging.warning(f"处理账号 {account} 时出错")
                    # 详细异常信息只记录到文件
                    logging.debug(f"处理账号 {account} 异常详情: {str(e)}", exc_info=True)
        finally:
            print("==================================")
            # 使用全局错误账号列表
            error_ap = get_error_accounts()
            print(f"密码错误的账号：{error_ap}")
            print(f"总计：{self.result_query}")
            # 清理所有会话
            session_manager.cleanup_all_sessions()




if __name__ == '__main__':
    # 使用绝对路径，无需切换目录
    #ap = filter.main()
    # 使用extract_data函数获取学号和密码数据
    ap = extract_data(["学号", "密码"])
    #ap = {'24408010206': ['24408010206']}
    #print(ap)

    # 创建Query实例，不需要账号密码参数
    query = Query("", "")  # 空参数，因为main方法中会为每个账号创建新实例
    main = query.main(ap)
