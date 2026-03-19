"""
异步爬虫基类
支持高并发爬取，自动限速、代理池
"""
import asyncio
from abc import abstractmethod
from typing import Optional, List, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import setup_logger, Parser, Storage
from utils.async_http_client import AsyncHttpClient
from utils.proxy_pool import ProxyPool


class AsyncCrawler:
    """异步爬虫基类"""
    
    def __init__(
        self,
        name: str = "async_crawler",
        timeout: int = 30,
        retry_times: int = 3,
        concurrent_limit: int = 10,
        request_delay: float = 0.5,
        output_format: str = "json",
        proxy_pool: Optional[ProxyPool] = None
    ):
        """
        初始化
        
        Args:
            name: 爬虫名称
            timeout: 请求超时
            retry_times: 重试次数
            concurrent_limit: 并发限制
            request_delay: 请求间隔（秒）
            output_format: 输出格式
            proxy_pool: 代理池
        """
        self.name = name
        self.http = AsyncHttpClient(
            timeout=timeout,
            retry_times=retry_times,
            concurrent_limit=concurrent_limit,
            proxy_pool=proxy_pool
        )
        self.parser = Parser()
        self.storage = Storage()
        self.output_format = output_format
        self.request_delay = request_delay
        self.logger = setup_logger(name)
        self.results: List[Dict] = []
        self._proxy_pool = proxy_pool
    
    @abstractmethod
    def start_urls(self) -> List[str]:
        """起始URL列表"""
        pass
    
    @abstractmethod
    async def parse(self, url: str, html: str) -> List[Dict]:
        """解析页面（异步）"""
        pass
    
    async def before_request(self, url: str) -> Optional[Dict]:
        """请求前的钩子"""
        return None
    
    async def after_parse(self, data: List[Dict]) -> List[Dict]:
        """解析后的钩子"""
        return data
    
    async def on_error(self, url: str, error: Exception):
        """错误处理钩子"""
        self.logger.error(f"处理 {url} 时出错: {error}")
    
    async def run(self) -> List[Dict]:
        """运行爬虫"""
        self.logger.info(f"异步爬虫 {self.name} 开始运行...")
        
        urls = self.start_urls()
        self.logger.info(f"共 {len(urls)} 个URL待爬取")
        
        await self.http.init_session()
        
        # 分批处理URL
        batch_size = self.http.concurrent_limit
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            tasks = [self._crawl_one(url) for url in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    self.results.extend(result)
            
            # 批次间延迟
            if i + batch_size < len(urls):
                await asyncio.sleep(self.request_delay)
        
        await self.http.close()
        
        self.logger.info(f"爬虫 {self.name} 完成，共获取 {len(self.results)} 条数据")
        
        return self.results
    
    async def _crawl_one(self, url: str) -> List[Dict]:
        """爬取单个URL"""
        try:
            # 请求前钩子
            await self.before_request(url)
            
            # 发送请求
            html = await self.http.fetch_text(url)
            if html is None:
                self.logger.warning(f"请求失败: {url}")
                return []
            
            # 解析页面
            data = await self.parse(url, html)
            
            # 解析后钩子
            data = await self.after_parse(data)
            
            self.logger.info(f"从 {url} 提取了 {len(data)} 条数据")
            
            return data
        
        except Exception as e:
            await self.on_error(url, e)
            return []
    
    def save(self, name: Optional[str] = None) -> str:
        """保存结果"""
        if name is None:
            name = self.name
        return self.storage.save(self.results, name, self.output_format)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = {
            "total_results": len(self.results),
            "proxy_pool": None
        }
        if self._proxy_pool:
            stats["proxy_pool"] = self._proxy_pool.get_stats()
        return stats


class AsyncSimpleCrawler(AsyncCrawler):
    """简单异步爬虫示例"""
    
    def __init__(
        self,
        urls: List[str],
        selectors: Dict[str, str],
        **kwargs
    ):
        """
        Args:
            urls: URL列表
            selectors: CSS选择器配置
        """
        super().__init__(name="async_simple_crawler", **kwargs)
        self.urls = urls
        self.selectors = selectors
    
    def start_urls(self) -> List[str]:
        return self.urls
    
    async def parse(self, url: str, html: str) -> List[Dict]:
        soup = self.parser.parse(html)
        results = []
        
        items_selector = self.selectors.get('items', 'body')
        items = self.parser.select(soup, items_selector)
        
        for item in items:
            data = {'source_url': url}
            
            for field, selector in self.selectors.items():
                if field == 'items':
                    continue
                
                element = item.select_one(selector) if selector else None
                if element:
                    if field in ['link', 'url', 'href']:
                        data[field] = element.get('href', '')
                    elif field in ['image', 'img', 'src']:
                        data[field] = element.get('src', '')
                    else:
                        data[field] = self.parser.extract_text(element)
                else:
                    data[field] = ''
            
            results.append(data)
        
        return results


# 使用示例
async def example():
    """使用示例"""
    # 创建代理池（可选）
    proxy_pool = ProxyPool(
        proxies=["http://127.0.0.1:7890"],  # 示例代理
        test_url="https://httpbin.org/ip"
    )
    
    # 创建爬虫
    crawler = AsyncSimpleCrawler(
        urls=[
            "https://httpbin.org/html",
            "https://httpbin.org/robots.txt",
        ],
        selectors={
            'items': 'body',
            'title': 'h1',
        },
        concurrent_limit=5,
        proxy_pool=proxy_pool  # 可选
    )
    
    # 运行
    results = await crawler.run()
    
    # 保存
    if results:
        filename = crawler.save()
        print(f"保存到: {filename}")
    
    print(f"统计: {crawler.get_stats()}")


if __name__ == "__main__":
    asyncio.run(example())