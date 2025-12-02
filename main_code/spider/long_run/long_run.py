import os
import sys
import requests
import datetime
import time
import random
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 统一使用 main_code 作为导入根目录，兼容直接运行和 -m 方式
CURRENT_FILE = Path(__file__).resolve()
MAIN_CODE_DIR = CURRENT_FILE.parents[2]  # .../main_code
if str(MAIN_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(MAIN_CODE_DIR))

# 统一的路径配置
from paths import SPIDER_LOGS_DIR

# 统一导入：所有模块都使用绝对导入（以 spider 为顶级包）
from spider.package.network.get_headers import get_headers
from spider.package.network.get_ip_port import get_ip_port
from spider.package.data import filter
from spider.package.data.query_spider import Query
from spider.package.auth.login import LoginConfig, create_authenticated_session
from spider.package.auth.session_manager import session_manager
from spider.package.core.common_utils import setup_logger, setup_root_logger
from spider.long_run.fake_key import encrypt_timestamp

# 配置 longrun 专用 logger（不需要配置根日志器，避免重复打印）
logger = setup_logger("longrun", str(SPIDER_LOGS_DIR / "longrun_log.txt"))

# 临时错误账号列表，用于存储超过12次重试失败的账号
temporary_error_accounts = []


def get_run_param(less_4km):
    """生成一套逻辑自洽的随机跑步参数（速度、里程、时间）"""
    speed_mps = random.uniform(2.21, 4.26)  # 随机速度 (m/s) 学校要求：1.5-5.5
    if less_4km == 1:
        mileage_km = random.uniform(3.88, 3.93)  # 小于4km的里程
        #logging.info("每天小于4km")
    else:
        mileage_km = random.uniform(4.13, 4.56)  # 大于4km的里程
        #logging.info("每天大于4km")

    pass_time_seconds = mileage_km * 1000 / speed_mps  # 根据里程和速度计算时长 (s)

    return {
        'speed': round(speed_mps, 2),
        'mileage': round(mileage_km, 2),
        'time': round(pass_time_seconds, 2)
    }


class RUN:
    def __init__(self):
        pass
        # 移除本地session对象，使用全局会话管理器

    def login(self, inner_account, inner_password):
        """使用统一的会话管理器进行登录"""
        # 获取代理IP
        proxies_list = get_ip_port()
        proxies = {}
        if proxies_list:
            proxy_ip = proxies_list[0]  # 使用第一个代理
            proxies = {
                'http': f'http://{proxy_ip}',
                'https': f'http://{proxy_ip}'
            }
            logger.info(f"使用代理IP: {proxy_ip}")
        else:
            logger.warning("未能获取到代理IP，将使用直连")
        
        # 配置登录参数，包括代理
        login_config = LoginConfig(
            timeout=5,
            retry_delay=2,
            use_proxy=True,
            proxies=proxies  # 添加代理配置
        )
        
        # 获取请求头
        headers = get_headers()
        
        # 使用统一的会话管理器创建认证会话
        session = create_authenticated_session(
            inner_account, 
            inner_password, 
            headers=headers,
            config=login_config
        )
        
        if session:
            logger.info("登录成功")
            # 将会话存储到会话管理器中
            session_manager._active_sessions[inner_account] = session
            session_manager._session_tokens[inner_account] = session.headers.get("Authorization", "").replace("Bearer ", "")
            session_manager._session_last_used[inner_account] = time.time()
            return session_manager._session_tokens[inner_account]
        else:
            logger.info(f"登录失败：{inner_account}")
            # 登录失败（12次重试后）添加到临时错误列表
            if [inner_account, inner_password] not in temporary_error_accounts:
                temporary_error_accounts.append([inner_account, inner_password])
                logger.debug(f"账号 {inner_account} 已添加到临时错误列表")
            return False

    def start(self, account, start_time_to_use, password=None):
        """发送开始跑步请求"""
        start_url = "https://lb.hnfnu.edu.cn/school/student/addLMRanking"
        # 生成操场内的随机经纬度
        dlatitude = round(random.uniform(28.195932, 28.197426), 6)
        # noinspection SpellCheckingInspection
        dlongitude = round(random.uniform(112.86050, 112.86125), 6)

        data = {
            "dlatitude": dlatitude,
            "dlongitude": dlongitude,
            "startTime": start_time_to_use
        }

        try:
            # 从会话管理器获取会话
            session = session_manager.get_session(account)
            if not session:
                logger.error(f"无法获取账号 {account} 的会话")
                # 添加到临时错误列表
                if password and [account, password] not in temporary_error_accounts:
                    temporary_error_accounts.append([account, password])
                    logger.debug(f"账号 {account} 因无法获取会话已添加到临时错误列表")
                return False
                
            # 使用会话进行请求
            start_respond = session.post(url=start_url, json=data, timeout=10)
            start_respond.raise_for_status()  # 检查HTTP错误
            response_json = start_respond.json()

            if response_json["msg"] == "操作成功":
                logger.info("开始跑步请求成功")
                return response_json  # 返回完整的json，包含data_id
            elif response_json["msg"] == "请求频繁！":
                logger.warning("提交开始时，出现请求频繁错误")
                # 请求频繁也需要添加到临时错误列表，下次重试
                if password and [account, password] not in temporary_error_accounts:
                    temporary_error_accounts.append([account, password])
                    logger.debug(f"账号 {account} 因请求频繁已添加到临时错误列表")
                return False
            else:
                logger.warning(f"开始跑步失败: {response_json.get('msg', '未知错误')}")
                # 添加到临时错误列表
                if password and [account, password] not in temporary_error_accounts:
                    temporary_error_accounts.append([account, password])
                    logger.debug(f"账号 {account} 因开始跑步失败已添加到临时错误列表")
                return False
        except requests.exceptions.RequestException as e:
            # 控制台只显示简短信息
            logger.warning("开始跑步请求异常，正在重试...")
            # 详细异常信息只记录到文件
            logger.debug(f"开始跑步请求异常详情: {str(e)}", exc_info=True)
            # 添加到临时错误列表
            if password and [account, password] not in temporary_error_accounts:
                temporary_error_accounts.append([account, password])
                logger.debug(f"账号 {account} 因请求异常已添加到临时错误列表")
            return False

    def start_and_finish(self, account, password, less_4km):
        """执行完整的开始和结束流程"""
        try:
            # 1. 生成所有跑步参数，确保数据一致性
            run_params = get_run_param(less_4km)
            mileage = run_params['mileage']
            speed = run_params['speed']
            pass_time_seconds = run_params['time']

            # 2. 计算所有时间点
            now = datetime.datetime.now()
            now_format = now.strftime("%Y-%m-%d %H:%M:%S")
            start_time = now - datetime.timedelta(seconds=pass_time_seconds)
            start_time_format = start_time.strftime("%Y-%m-%d %H:%M:%S")

            # 将秒数转换为 HH:MM:SS 或 MM:SS 格式的字符串
            hours, remainder = divmod(int(pass_time_seconds), 3600)
            minutes, seconds = divmod(remainder, 60)
            passtime = f"{minutes:02d}:{seconds:02d}" if not hours else f"{hours:02d}:{minutes:02d}:{seconds:02d}"

            logger.info(f"里程：{mileage}km；时长：{passtime}；速度：{speed}m/s")

            # 3. 调用 start() 函数
            start_respond_json = self.start(account, start_time_format, password)

            if start_respond_json and start_respond_json.get("msg") == "操作成功":
                data_id = start_respond_json["data"]
            else:
                logger.error("开始跑步失败，终止本次操作")
                # start() 函数内部已经处理了临时错误列表，这里不需要重复添加
                return

            # 4. 准备结束请求
            finish_url = "https://lb.hnfnu.edu.cn/school/student/longMarchSpeed"

            # 在发送请求前一刻生成加密数据，保证时间戳新鲜度
            encrypted_data = encrypt_timestamp()
            custom_header = encrypted_data["custom-header"]
            body_part = encrypted_data["bodyPart"]

            data_to_submit = {
                "id": data_id,
                "state": "等待",
                "mileage": mileage,
                "mileageSum": mileage,
                "formattedTime": f"{passtime}",
                "overTime": f"{now_format}",
                "speed": f"{speed}",
                "bodyPart": f"{body_part}"
            }

            # 从会话管理器获取会话
            session = session_manager.get_session(account)
            if not session:
                logger.error(f"无法获取账号 {account} 的会话")
                return

            # 为结束请求构建一个独立的、完整的临时请求头
            finish_headers = dict(session.headers)
            finish_headers.update({
                "custom-header": custom_header,
                "Content-Type": "application/json"
            })

            try:
                finish_respond = session.post(headers=finish_headers, url=finish_url, json=data_to_submit,
                                                   timeout=10)
                finish_respond.raise_for_status()
                j_respond = finish_respond.json()
                msg = j_respond["msg"]

                if msg == "操作成功":
                    logger.info("结束跑步请求成功")
                    filter.add_one(account)
                elif msg == "每天最多4公里，您今天已完成4.0公里":
                    logger.info("今天已完成4.0公里")
                    filter.add_one(account)
                elif "工具调用" in msg:  # 使用 in 判断，更健壮
                    logger.error(f"结束响应为工具调用: {msg}")
                    # 工具调用错误也需要添加到临时错误列表
                    if [account, password] not in temporary_error_accounts:
                        temporary_error_accounts.append([account, password])
                        logger.debug(f"账号 {account} 因工具调用错误已添加到临时错误列表")
                else:
                    logger.error(f"结束失败: {msg}")
                    # 其他结束失败也需要添加到临时错误列表
                    if [account, password] not in temporary_error_accounts:
                        temporary_error_accounts.append([account, password])
                        logger.debug(f"账号 {account} 因结束跑步失败已添加到临时错误列表")
            except requests.exceptions.RequestException as e:
                # 控制台只显示简短信息
                logger.warning("结束跑步请求异常")
                # 详细异常信息只记录到文件
                logger.debug(f"结束跑步请求异常详情: {str(e)}", exc_info=True)
                # 请求异常也需要添加到临时错误列表
                if [account, password] not in temporary_error_accounts:
                    temporary_error_accounts.append([account, password])
                    logger.debug(f"账号 {account} 因结束请求异常已添加到临时错误列表")

        except Exception as e:
            # 捕获所有其他未知异常
            # 控制台只显示简短信息
            logger.critical("start_and_finish 发生未知严重错误")
            # 详细异常信息只记录到文件
            logger.debug(f"start_and_finish 异常详情: {str(e)}", exc_info=True)
            # 未知异常也需要添加到临时错误列表
            if [account, password] not in temporary_error_accounts:
                temporary_error_accounts.append([account, password])
                logger.debug(f"账号 {account} 因未知异常已添加到临时错误列表")

    def logout(self, account):
        """使用统一的会话管理器退出登录"""
        session_manager.logout_session(account)
        logger.info(f"账号 {account} 已退出登录")

    def query_and_update_mileage(self, account, token):
        """查询并更新里程记录"""
        try:
            # 从会话管理器获取会话
            session = session_manager.get_session(account)
            if not session:
                logger.error(f"无法获取账号 {account} 的会话")
                return

            # 确保Authorization头正确设置
            session.headers.update({
                "Authorization": f"Bearer {token}"
            })

            # 请求记录页面url
            mileage_url = "https://lb.hnfnu.edu.cn/school/student/getMyLongMarchList"
            respond_json = session.get(mileage_url, timeout=10).json()

            # 检查响应是否包含rows字段
            if not respond_json.get('rows'):
                logger.warning(f"账号 {account} 查询记录失败，API响应: {respond_json}")
                return

            # 如果有响应就获取并更新名字
            if respond_json['rows']:
                name = respond_json['rows'][0]['studentName']
                logger.info(f"姓名：{name}")
                # 更新account_name.json
                from paths import ACCOUNT_NAME_FILE, CURRENT_MILEAGE_FILE
                import json
                try:
                    with open(ACCOUNT_NAME_FILE, 'r', encoding='utf-8') as f:
                        account_names = json.load(f)
                    account_names[account] = name
                    with open(ACCOUNT_NAME_FILE, 'w', encoding='utf-8') as f:
                        json.dump(account_names, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    logger.debug(f"更新账号名称失败: {str(e)}")

                # 获取记录数据
                mileages = [item["mileage"] for item in respond_json["rows"]]
                mileages_sum = sum(mileages)
                logger.info(f"当前里程：{round(mileages_sum, 2)}")

                # 更新current_mileage.json
                try:
                    with open(CURRENT_MILEAGE_FILE, 'r', encoding='utf-8') as f:
                        current_mileage = json.load(f)
                    current_mileage[account] = mileages_sum
                    with open(CURRENT_MILEAGE_FILE, 'w', encoding='utf-8') as f:
                        json.dump(current_mileage, f, ensure_ascii=False, indent=4)
                except Exception as e:
                    logger.debug(f"更新里程数据失败: {str(e)}")

        except requests.exceptions.RequestException as e:
            logger.warning(f"查询记录请求异常")
            logger.debug(f"查询记录异常详情: {str(e)}", exc_info=True)
        except Exception as e:
            logger.warning(f"查询记录时发生错误")
            logger.debug(f"查询记录错误详情: {str(e)}", exc_info=True)

    def main(self, accounts=None):
        """主执行逻辑，遍历所有账号并执行跑步流程"""
        # 如果没有提供账号列表，则使用filter.main()获取需要长征跑的用户
        if accounts is None:
            user_details = filter.main()
            accounts = [[account, details[0]] for account, details in user_details.items()]
            logger.info(f"经过筛选后需要执行的用户数量: {len(accounts)}")
        
        # 添加临时错误列表中的账号到处理列表（如果不在主列表中）
        for error_account in temporary_error_accounts:
            if error_account not in accounts:
                accounts.append(error_account)
                logger.debug(f"从临时错误列表添加账号: {error_account[0]}")
        
        account_len = len(accounts)
        logger.info(f"本次执行数量: {account_len} (包括{len(temporary_error_accounts)}个临时错误账号)")
        index = 1
        success_count = 0
        
        for account, password in accounts:
            # 从user_details中获取less_4km参数
            less_4km = 0  # 默认值
            if account in user_details:
                less_4km = user_details[account][2] if len(user_details[account]) > 2 else 0

            loop_now = time.time()
            logger.info("-----------------------------")
            logger.info(f"({index}/{account_len})")
            logger.info(f"( 当前学号: {account};密码 {password})")

            # 检查是否是临时错误账号
            is_temp_error = [account, password] in temporary_error_accounts
            if is_temp_error:
                logger.debug(f"账号 {account} 来自临时错误列表，正在重试")

            login_token = self.login(account, password)

            if login_token:
                self.start_and_finish(account, password, less_4km)
                # 直接使用当前session查询记录，不创建新的Query实例
                self.query_and_update_mileage(account, login_token)
                success_count += 1
                
                # 如果是临时错误账号且登录成功，从临时错误列表中移除
                if is_temp_error and [account, password] in temporary_error_accounts:
                    temporary_error_accounts.remove([account, password])
                    logger.info(f"账号 {account} 已从临时错误列表中移除")
            else:
                logger.debug(f"账号 {account} 处理失败")
                # 登录失败已经在login方法中处理了临时错误列表，这里不需要额外处理

            # 无论登录是否成功，都要清理会话状态
            self.logout(account)  # 使用统一的会话管理器清理会话状态

            index += 1
            loop_end = time.time()
            elapsed = loop_end - loop_now
            logger.info(f"该账号处理完成，耗时：{round(elapsed, 2)}s")

        failed_count = len(accounts) - success_count
        logger.info(f"本轮成功账号：{success_count}，失败账号：{failed_count}")
        
        # 记录临时错误列表状态，列出所有失败账号的学号
        if temporary_error_accounts:
            # 列出所有失败账号的学号，便于查看
            all_error_accounts = [acc[0] for acc in temporary_error_accounts]
            error_accounts_str = ", ".join(all_error_accounts)
            logger.info(f"临时错误列表中有 {len(temporary_error_accounts)} 个账号: {error_accounts_str}")
            
            # 同时记录到调试日志中，便于后续分析
            logger.debug(f"完整临时错误列表: {temporary_error_accounts}")
        else:
            logger.info("临时错误列表为空")
            
        return failed_count


def main():
    """脚本入口，控制主循环和重试逻辑"""
    # 确保工作目录正确
    # 项目根目录已定义为常量，无需动态推导
    pass
    # logging_config()  # 已被统一日志配置替代
    total_start_time = time.time()
    i = 1
    try:
        while True:
            logger.info("==============================================")
            logger.info(f"第 {i} 次运行脚本")
            instance = RUN()
            try:
                failed_count = instance.main()
            except Exception as e:
                logger.error(f"执行过程中发生异常: {str(e)}")
                logger.debug(f"异常详情: {str(e)}", exc_info=True)
                failed_count = -1  # 使用-1表示异常情况

            # 如果有失败账号且未达到最大重试次数，则等待后重试
            if failed_count > 0 and i < 10:
                i += 1
                wait_time = 60 * i
                logger.info(f"存在失败账号，等待 {wait_time} 秒后进行第 {i} 次重试...")
                time.sleep(wait_time)
            else:
                logger.info("==============================================")
                if failed_count == 0:
                    logger.info("所有账号均已成功，脚本完成。")
                elif failed_count < 0:
                    logger.warning("执行过程中发生异常，但脚本将继续运行。")
                else:
                    logger.warning("已达到最大重试次数(10次)，脚本结束。")
                break
    finally:
        # 确保所有会话都被清理
        session_manager.cleanup_all_sessions()
        logger.info("所有会话已清理")

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    logger.info(f"总耗时：{int(total_duration // 60)}min {int(total_duration % 60)}s")


if __name__ == '__main__':
    main()
