import json
import random
import requests
import hashlib
# 提取订单
"""
    orderId:提取订单号
    secret:用户密钥
    num:提取IP个数
    pid:省份
    cid:城市
    type：请求类型，1=http/https,2=socks5
    unbindTime:使用时长，秒/s为单位
    noDuplicate:去重，0=不去重，1=去重
    lineSeparator:分隔符
    singleIp:切换,0=切换，1=不切换
"""
def get_ip_port():
    import time
    orderId = "O25032517363720614683"
    secret = "2f2bb84cc5074535aba6627ce95fb911"
    num = "1"
    pid = "-1"
    cid = ""
    type = "1"
    unbindTime = "60"
    noDuplicate = "0"
    lineSeparator = "0"
    singleIp = "0"
    time = str(int(time.time())) #时间戳

    # 计算sign
    txt = "orderId=" + orderId + "&" + "secret=" + secret + "&" + "time=" + time
    sign = hashlib.md5(txt.encode()).hexdigest()
    # 访问URL获取IP
    url = "http://api.hailiangip.com:8422/api/getIp?type=1" + "&num=" + num + "&pid=" + pid + "&unbindTime=" + unbindTime + "&cid=" + cid +  "&orderId=" + orderId + "&time=" + time + "&sign=" + sign + "&dataType=0" + "&lineSeparator=" + lineSeparator + "&noDuplicate=" + noDuplicate + "&singleIp=" + singleIp
    my_response = requests.get(url).content

    #获取响应数据
    dc_res = json.loads(my_response)
    #获取data列表
    ip_dict_list = dc_res["data"]
    #提取列表的字典
    ip_dict_list = [f"{ip_dc['ip']}:{ip_dc['port']}" for ip_dc in ip_dict_list]
    return ip_dict_list



if __name__ == '__main__':
    ip_poor = get_ip_port()
    print(ip_poor)

