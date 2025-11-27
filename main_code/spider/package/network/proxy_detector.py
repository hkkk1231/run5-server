#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IP代理失效检测模块
用于检测连续获取的代理IP是否重复，判断代理服务是否失效
"""

import json
import os
import sys
from typing import List, Dict, Optional

# 使用统一的绝对路径配置
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from paths import SPIDER_DATA_DIR

class ProxyFailureDetector:
    """代理失效检测器"""
    
    def __init__(self, history_file: Optional[str] = None, max_duplicate_count: int = 20):
        """
        初始化代理失效检测器
        
        Args:
            history_file: IP历史记录文件路径
            max_duplicate_count: 最大重复次数，超过此次数认为代理失效
        """
        self.max_duplicate_count = max_duplicate_count
        self.history_file = history_file or str(SPIDER_DATA_DIR / "proxy_history.json")
        self.ip_history: List[Dict[str, str]] = []
        self._load_history()
    
    def _load_history(self):
        """加载IP历史记录"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.ip_history = json.load(f)
        except Exception as e:
            print(f"加载IP历史记录失败: {e}")
            self.ip_history = []
    
    def _save_history(self):
        """保存IP历史记录"""
        try:
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.ip_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存IP历史记录失败: {e}")
    
    def add_ip(self, ip: str, timestamp: Optional[str] = None):
        """
        添加新的IP记录
        
        Args:
            ip: 代理IP地址
            timestamp: 时间戳，如果不提供则使用当前时间
        """
        import time
        
        if timestamp is None:
            timestamp = str(int(time.time()))
        
        # 添加新记录
        self.ip_history.append({
            "ip": ip,
            "timestamp": timestamp
        })
        
        # 只保留最近50条记录
        if len(self.ip_history) > 50:
            self.ip_history = self.ip_history[-50:]
        
        # 保存历史记录
        self._save_history()
    
    def check_proxy_failure(self) -> bool:
        """
        检查代理是否失效
        
        Returns:
            True表示代理失效，False表示代理正常
        """
        if len(self.ip_history) < self.max_duplicate_count:
            return False
        
        # 检查最近max_duplicate_count条记录是否都是同一个IP
        recent_ips = [record["ip"] for record in self.ip_history[-self.max_duplicate_count:]]
        if len(set(recent_ips)) == 1:
            # 所有IP都相同，代理可能失效
            duplicate_ip = recent_ips[0]
            print(f"⚠️ IP代理失效警告：连续{self.max_duplicate_count}次获取到相同IP: {duplicate_ip}")
            return True
        
        return False
    
    def get_recent_ips(self, count: int = 10) -> List[str]:
        """
        获取最近的IP记录
        
        Args:
            count: 获取的数量
            
        Returns:
            最近的IP列表
        """
        return [record["ip"] for record in self.ip_history[-count:]]
    
    def clear_history(self):
        """清空历史记录"""
        self.ip_history = []
        self._save_history()


# 全局检测器实例
_detector = None

def get_detector() -> ProxyFailureDetector:
    """获取全局检测器实例"""
    global _detector
    if _detector is None:
        _detector = ProxyFailureDetector()
    return _detector

def check_and_add_ip(ip: str) -> bool:
    """
    检查并添加IP
    
    Args:
        ip: 代理IP地址
        
    Returns:
        True表示代理正常，False表示代理失效
    """
    detector = get_detector()
    detector.add_ip(ip)
    
    if detector.check_proxy_failure():
        print("❌ IP代理失效，程序退出")
        sys.exit(1)
    
    return True

if __name__ == "__main__":
    # 测试代码
    detector = ProxyFailureDetector()
    
    # 测试正常情况
    test_ips = ["192.168.1.1:8080", "192.168.1.2:8080", "192.168.1.3:8080"]
    for ip in test_ips:
        detector.add_ip(ip)
        print(f"添加IP: {ip}, 代理状态: {'正常' if not detector.check_proxy_failure() else '失效'}")
    
    # 测试失效情况
    duplicate_ip = "192.168.1.100:8080"
    for i in range(21):
        detector.add_ip(duplicate_ip)
        status = detector.check_proxy_failure()
        print(f"添加IP {duplicate_ip} (第{i+1}次), 代理状态: {'正常' if not status else '失效'}")
        if status:
            break