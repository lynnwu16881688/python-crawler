"""
代理池管理
支持多种代理来源：文件、API、自定义列表
自动检测代理可用性
"""
import time
import random
import requests
from typing import List, Dict, Optional
from threading import Lock
from queue import Queue
import os


class ProxyPool:
    """代理池管理类"""
    
    def __init__(
        self,
        proxies: Optional[List[str]] = None,
        proxy_file: Optional[str] = None,
        proxy_api: Optional[str] = None,
        test_url: str = "https://httpbin.org/ip",
        timeout: int = 10,
        min_score: int = 50,
        check_interval: int = 300
    ):
        """
        初始化代理池
        
        Args:
            proxies: 代理列表 ["http://ip:port", ...]
            proxy_file: 代理文件路径（每行一个代理）
            proxy_api: 代理API地址
            test_url: 测试代理可用性的URL
            timeout: 代理测试超时时间
            min_score: 代理最低分数（低于此分数的代理会被移除）
            check_interval: 自动检查间隔（秒）
        """
        self.test_url = test_url
        self.timeout = timeout
        self.min_score = min_score
        self.check_interval = check_interval
        
        # 代理存储：{proxy: {"score": 100, "last_check": timestamp, "fail_count": 0}}
        self._pool: Dict[str, Dict] = {}
        self._lock = Lock()
        self._queue = Queue()  # 可用代理队列
        
        # 加载代理
        if proxies:
            self.add_proxies(proxies)
        if proxy_file:
            self.load_from_file(proxy_file)
        if proxy_api:
            self.load_from_api(proxy_api)
    
    def add_proxies(self, proxies: List[str]) -> int:
        """添加代理列表"""
        added = 0
        with self._lock:
            for proxy in proxies:
                proxy = proxy.strip()
                if proxy and proxy not in self._pool:
                    self._pool[proxy] = {
                        "score": 100,
                        "last_check": 0,
                        "fail_count": 0
                    }
                    self._queue.put(proxy)
                    added += 1
        return added
    
    def load_from_file(self, filepath: str) -> int:
        """从文件加载代理"""
        if not os.path.exists(filepath):
            return 0
        
        proxies = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    # 支持格式：ip:port 或 protocol://ip:port
                    if '://' not in line:
                        line = f"http://{line}"
                    proxies.append(line)
        
        return self.add_proxies(proxies)
    
    def load_from_api(self, api_url: str, count: int = 20) -> int:
        """从API获取代理"""
        try:
            response = requests.get(api_url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                
                # 支持多种API格式
                proxies = []
                if isinstance(data, list):
                    # 格式1: ["ip:port", ...] 或 [{"ip": "...", "port": ...}, ...]
                    for item in data[:count]:
                        if isinstance(item, str):
                            if '://' not in item:
                                item = f"http://{item}"
                            proxies.append(item)
                        elif isinstance(item, dict):
                            ip = item.get('ip', item.get('host', ''))
                            port = item.get('port', '')
                            protocol = item.get('protocol', 'http')
                            if ip and port:
                                proxies.append(f"{protocol}://{ip}:{port}")
                elif isinstance(data, dict):
                    # 格式2: {"data": [...]}
                    items = data.get('data', data.get('proxies', []))
                    for item in items[:count]:
                        if isinstance(item, str):
                            if '://' not in item:
                                item = f"http://{item}"
                            proxies.append(item)
                        elif isinstance(item, dict):
                            ip = item.get('ip', item.get('host', ''))
                            port = item.get('port', '')
                            protocol = item.get('protocol', 'http')
                            if ip and port:
                                proxies.append(f"{protocol}://{ip}:{port}")
                
                return self.add_proxies(proxies)
        except Exception as e:
            print(f"从API获取代理失败: {e}")
        
        return 0
    
    def get(self) -> Optional[str]:
        """获取一个代理（随机选择）"""
        with self._lock:
            if not self._pool:
                return None
            
            # 获取分数较高的代理
            valid_proxies = [
                p for p, info in self._pool.items()
                if info["score"] >= self.min_score
            ]
            
            if not valid_proxies:
                # 如果没有高分代理，返回任意一个
                valid_proxies = list(self._pool.keys())
            
            # 加权随机选择（分数越高，权重越大）
            weights = [self._pool[p]["score"] for p in valid_proxies]
            total = sum(weights)
            if total == 0:
                return random.choice(valid_proxies)
            
            r = random.randint(1, total)
            current = 0
            for proxy in valid_proxies:
                current += self._pool[proxy]["score"]
                if current >= r:
                    return proxy
        
        return None
    
    def report_success(self, proxy: str):
        """报告代理使用成功"""
        with self._lock:
            if proxy in self._pool:
                self._pool[proxy]["fail_count"] = 0
                # 成功加分，最高100分
                self._pool[proxy]["score"] = min(100, self._pool[proxy]["score"] + 5)
    
    def report_failure(self, proxy: str):
        """报告代理使用失败"""
        with self._lock:
            if proxy in self._pool:
                self._pool[proxy]["fail_count"] += 1
                self._pool[proxy]["score"] -= 10
                
                # 连续失败3次或分数过低，移除代理
                if (self._pool[proxy]["fail_count"] >= 3 or 
                    self._pool[proxy]["score"] < self.min_score - 20):
                    del self._pool[proxy]
    
    def check_proxy(self, proxy: str) -> bool:
        """检测代理是否可用"""
        try:
            response = requests.get(
                self.test_url,
                proxies={"http": proxy, "https": proxy},
                timeout=self.timeout
            )
            if response.status_code == 200:
                self.report_success(proxy)
                return True
        except:
            pass
        
        self.report_failure(proxy)
        return False
    
    def check_all(self) -> Dict[str, int]:
        """检测所有代理"""
        results = {"success": 0, "failed": 0, "removed": 0}
        
        with self._lock:
            proxies = list(self._pool.keys())
        
        for proxy in proxies:
            if self.check_proxy(proxy):
                results["success"] += 1
            else:
                results["failed"] += 1
                with self._lock:
                    if proxy not in self._pool:
                        results["removed"] += 1
        
        return results
    
    def size(self) -> int:
        """获取代理池大小"""
        return len(self._pool)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            if not self._pool:
                return {"total": 0, "valid": 0, "avg_score": 0}
            
            scores = [info["score"] for info in self._pool.values()]
            valid = sum(1 for s in scores if s >= self.min_score)
            
            return {
                "total": len(self._pool),
                "valid": valid,
                "avg_score": sum(scores) / len(scores)
            }
    
    def clear(self):
        """清空代理池"""
        with self._lock:
            self._pool.clear()
            while not self._queue.empty():
                self._queue.get()
    
    def save_to_file(self, filepath: str):
        """保存代理到文件"""
        with self._lock:
            valid_proxies = [
                p for p, info in self._pool.items()
                if info["score"] >= self.min_score
            ]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for proxy in valid_proxies:
                f.write(f"{proxy}\n")


# 使用示例
if __name__ == "__main__":
    # 示例：创建代理池
    pool = ProxyPool(
        proxies=[
            "http://127.0.0.1:7890",
            "http://127.0.0.1:8080",
        ],
        proxy_file="proxies.txt",  # 可选：从文件加载
        # proxy_api="http://api.proxy.com/get?num=20",  # 可选：从API获取
    )
    
    print(f"代理池大小: {pool.size()}")
    print(f"统计信息: {pool.get_stats()}")
    
    # 获取代理
    proxy = pool.get()
    print(f"获取代理: {proxy}")
    
    # 报告结果
    # pool.report_success(proxy)
    # pool.report_failure(proxy)