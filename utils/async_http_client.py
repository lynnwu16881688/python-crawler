"""
异步HTTP客户端
基于aiohttp，支持并发请求、代理、自动重试
"""
import asyncio
import aiohttp
import random
import time
from typing import Optional, Dict, List, Any, Callable
from fake_useragent import UserAgent
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.proxy_pool import ProxyPool


class AsyncHttpClient:
    """异步HTTP客户端"""
    
    def __init__(
        self,
        timeout: int = 30,
        retry_times: int = 3,
        retry_delay: float = 1.0,
        concurrent_limit: int = 10,
        proxy_pool: Optional[ProxyPool] = None
    ):
        """
        初始化
        
        Args:
            timeout: 请求超时时间
            retry_times: 重试次数
            retry_delay: 重试延迟
            concurrent_limit: 并发限制
            proxy_pool: 代理池实例
        """
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.retry_times = retry_times
        self.retry_delay = retry_delay
        self.concurrent_limit = concurrent_limit
        self.proxy_pool = proxy_pool
        self.ua = UserAgent()
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._session: Optional[aiohttp.ClientSession] = None
    
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
    
    async def _get_proxy(self) -> Optional[str]:
        """获取代理"""
        if self.proxy_pool:
            return self.proxy_pool.get()
        return None
    
    async def _report_proxy_result(self, proxy: str, success: bool):
        """报告代理结果"""
        if self.proxy_pool and proxy:
            if success:
                self.proxy_pool.report_success(proxy)
            else:
                self.proxy_pool.report_failure(proxy)
    
    async def init_session(self):
        """初始化会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
            self._semaphore = asyncio.Semaphore(self.concurrent_limit)
    
    async def close(self):
        """关闭会话"""
        if self._session and not self._session.closed:
            await self._session.close()
    
    async def get(
        self,
        url: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Optional[aiohttp.ClientResponse]:
        """GET请求"""
        await self.init_session()
        
        for attempt in range(self.retry_times):
            proxy = await self._get_proxy()
            
            async with self._semaphore:
                try:
                    response = await self._session.get(
                        url,
                        params=params,
                        headers=self._get_headers(headers),
                        proxy=proxy,
                        **kwargs
                    )
                    response.raise_for_status()
                    await self._report_proxy_result(proxy, True)
                    return response
                
                except asyncio.CancelledError:
                    raise
                
                except Exception as e:
                    await self._report_proxy_result(proxy, False)
                    
                    if attempt < self.retry_times - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        print(f"请求失败: {url}, 错误: {e}")
                        return None
    
    async def post(
        self,
        url: str,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        **kwargs
    ) -> Optional[aiohttp.ClientResponse]:
        """POST请求"""
        await self.init_session()
        
        for attempt in range(self.retry_times):
            proxy = await self._get_proxy()
            
            async with self._semaphore:
                try:
                    response = await self._session.post(
                        url,
                        data=data,
                        json=json,
                        headers=self._get_headers(headers),
                        proxy=proxy,
                        **kwargs
                    )
                    response.raise_for_status()
                    await self._report_proxy_result(proxy, True)
                    return response
                
                except asyncio.CancelledError:
                    raise
                
                except Exception as e:
                    await self._report_proxy_result(proxy, False)
                    
                    if attempt < self.retry_times - 1:
                        await asyncio.sleep(self.retry_delay * (attempt + 1))
                    else:
                        print(f"请求失败: {url}, 错误: {e}")
                        return None
    
    async def fetch_text(
        self,
        url: str,
        encoding: Optional[str] = None,
        **kwargs
    ) -> Optional[str]:
        """获取页面文本"""
        response = await self.get(url, **kwargs)
        if response:
            text = await response.text(encoding=encoding)
            return text
        return None
    
    async def fetch_json(
        self,
        url: str,
        **kwargs
    ) -> Optional[Any]:
        """获取JSON数据"""
        response = await self.get(url, **kwargs)
        if response:
            return await response.json()
        return None
    
    async def fetch_all(
        self,
        urls: List[str],
        callback: Optional[Callable[[str, str], Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        批量请求多个URL
        
        Args:
            urls: URL列表
            callback: 回调函数 (url, text) -> result
            **kwargs: 传递给get的额外参数
        
        Returns:
            {url: result} 字典
        """
        await self.init_session()
        results = {}
        
        async def fetch_one(url: str):
            text = await self.fetch_text(url, **kwargs)
            if text:
                if callback:
                    results[url] = callback(url, text)
                else:
                    results[url] = text
            else:
                results[url] = None
        
        tasks = [fetch_one(url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
    
    async def __aenter__(self):
        await self.init_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class AsyncRequest:
    """异步请求上下文管理器，简化使用"""
    
    def __init__(
        self,
        concurrent_limit: int = 10,
        proxy_pool: Optional[ProxyPool] = None
    ):
        self.client = AsyncHttpClient(
            concurrent_limit=concurrent_limit,
            proxy_pool=proxy_pool
        )
    
    async def get(self, url: str, **kwargs) -> Optional[str]:
        return await self.client.fetch_text(url, **kwargs)
    
    async def post(self, url: str, **kwargs) -> Optional[aiohttp.ClientResponse]:
        return await self.client.post(url, **kwargs)
    
    async def fetch_all(self, urls: List[str], **kwargs) -> Dict[str, Any]:
        return await self.client.fetch_all(urls, **kwargs)
    
    async def __aenter__(self):
        await self.client.init_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.close()


# 使用示例
async def example():
    """使用示例"""
    # 基本使用
    async with AsyncRequest(concurrent_limit=5) as req:
        # 单个请求
        html = await req.get("https://httpbin.org/ip")
        print(f"页面内容: {html[:200]}...")
        
        # 批量请求
        urls = [
            "https://httpbin.org/delay/1",
            "https://httpbin.org/delay/2",
            "https://httpbin.org/delay/1",
        ]
        results = await req.fetch_all(urls)
        print(f"获取了 {len(results)} 个页面")


if __name__ == "__main__":
    asyncio.run(example())