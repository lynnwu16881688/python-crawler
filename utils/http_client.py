"""
HTTP客户端工具
支持requests和aiohttp，自动重试、代理、User-Agent轮换
"""
import time
import random
import requests
from typing import Optional, Dict, Any
from fake_useragent import UserAgent


class HttpClient:
    """HTTP客户端类"""
    
    def __init__(
        self,
        timeout: int = 30,
        retry_times: int = 3,
        retry_delay: int = 2,
        proxy: Optional[str] = None
    ):
        self.timeout = timeout
        self.retry_times = retry_times
        self.retry_delay = retry_delay
        self.proxy = proxy
        self.ua = UserAgent()
        self.session = requests.Session()
        
    def _get_headers(self, custom_headers: Optional[Dict] = None) -> Dict[str, str]:
        """生成请求头"""
        headers = {
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        if custom_headers:
            headers.update(custom_headers)
        return headers
    
    def get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Optional[requests.Response]:
        """GET请求"""
        for attempt in range(self.retry_times):
            try:
                proxies = {'http': self.proxy, 'https': self.proxy} if self.proxy else None
                response = self.session.get(
                    url,
                    params=params,
                    headers=self._get_headers(headers),
                    timeout=self.timeout,
                    proxies=proxies,
                    **kwargs
                )
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_delay)
                else:
                    print(f"请求失败: {url}, 错误: {e}")
                    return None
    
    def post(
        self,
        url: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Optional[requests.Response]:
        """POST请求"""
        for attempt in range(self.retry_times):
            try:
                proxies = {'http': self.proxy, 'https': self.proxy} if self.proxy else None
                response = self.session.post(
                    url,
                    data=data,
                    json=json,
                    headers=self._get_headers(headers),
                    timeout=self.timeout,
                    proxies=proxies,
                    **kwargs
                )
                response.raise_for_status()
                return response
            except Exception as e:
                if attempt < self.retry_times - 1:
                    time.sleep(self.retry_delay)
                else:
                    print(f"请求失败: {url}, 错误: {e}")
                    return None
    
    def close(self):
        """关闭会话"""
        self.session.close()