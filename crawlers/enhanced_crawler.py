"""
增强版异步爬虫 - 集成所有高级功能
支持：断点续爬、URL去重、代理池、验证码识别
"""
import asyncio
from typing import Optional, List, Dict, Any, Callable
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import (
    setup_logger, Parser, Storage, 
    AsyncHttpClient, ProxyPool,
    TaskManager, BrowserCrawler, CaptchaManager
)


class EnhancedCrawler:
    """增强版爬虫"""
    
    def __init__(
        self,
        name: str = "enhanced_crawler",
        data_dir: str = "./tasks",
        concurrent_limit: int = 10,
        request_delay: float = 0.5,
        retry_times: int = 3,
        use_proxy: bool = False,
        proxy_pool: Optional[ProxyPool] = None,
        output_format: str = "json",
        enable_browser: bool = False,
        browser_headless: bool = True
    ):
        """
        初始化增强版爬虫
        
        Args:
            name: 爬虫名称
            data_dir: 数据目录
            concurrent_limit: 并发限制
            request_delay: 请求间隔
            retry_times: 重试次数
            use_proxy: 是否使用代理
            proxy_pool: 代理池实例
            output_format: 输出格式
            enable_browser: 是否启用浏览器模式
            browser_headless: 浏览器是否无头
        """
        self.name = name
        self.concurrent_limit = concurrent_limit
        self.request_delay = request_delay
        self.retry_times = retry_times
        self.output_format = output_format
        
        # 日志
        self.logger = setup_logger(name)
        
        # 任务管理器（支持断点续爬）
        self.task_manager = TaskManager(name, data_dir)
        
        # HTTP客户端
        self.http = AsyncHttpClient(
            retry_times=retry_times,
            concurrent_limit=concurrent_limit,
            proxy_pool=proxy_pool if use_proxy else None
        )
        
        # 浏览器爬虫（可选）
        self.enable_browser = enable_browser
        self.browser_headless = browser_headless
        self.browser: Optional[BrowserCrawler] = None
        
        # 代理池
        self.proxy_pool = proxy_pool
        
        # 解析器和存储
        self.parser = Parser()
        self.storage = Storage()
        
        # 结果
        self.results: List[Dict] = []
    
    async def init(self):
        """初始化"""
        await self.http.init_session()
        
        if self.enable_browser:
            self.browser = BrowserCrawler(
                name=f"{self.name}_browser",
                headless=self.browser_headless
            )
            await self.browser.start()
    
    async def close(self):
        """关闭资源"""
        await self.http.close()
        
        if self.browser:
            await self.browser.close()
    
    def add_urls(self, urls: List[str]) -> int:
        """
        添加URL列表（自动去重）
        
        Returns:
            新增URL数量
        """
        return len(self.task_manager.add_urls(urls))
    
    def get_progress(self) -> Dict:
        """获取进度"""
        return self.task_manager.get_progress()
    
    def resume(self) -> List[str]:
        """
        恢复未完成的任务
        
        Returns:
            待处理的URL列表
        """
        # 获取待处理的URL
        pending = self.task_manager.get_pending_urls()
        
        # 重试失败的任务
        retry_urls = self.task_manager.retry_failed(self.retry_times)
        
        return pending + retry_urls
    
    async def crawl_page(self, url: str) -> Optional[str]:
        """
        爬取单个页面
        
        Args:
            url: 页面URL
        
        Returns:
            页面HTML
        """
        self.task_manager.mark_running(url)
        
        try:
            if self.enable_browser and self.browser:
                # 使用浏览器爬取（支持JavaScript）
                await self.browser.goto(url)
                html = await self.browser.get_content()
            else:
                # 使用HTTP客户端爬取
                html = await self.http.fetch_text(url)
            
            if html:
                self.task_manager.mark_completed(url)
            else:
                self.task_manager.mark_failed(url, "Empty response")
            
            return html
        
        except Exception as e:
            self.task_manager.mark_failed(url, str(e))
            self.logger.error(f"爬取失败: {url}, 错误: {e}")
            return None
    
    async def run(
        self,
        parse_func: Optional[Callable[[str, str], List[Dict]]] = None
    ) -> List[Dict]:
        """
        运行爬虫
        
        Args:
            parse_func: 解析函数 (url, html) -> List[Dict]
        
        Returns:
            爬取结果列表
        """
        await self.init()
        
        # 获取待处理的URL
        urls = self.resume()
        
        if not urls:
            self.logger.info("没有待处理的URL")
            return []
        
        self.logger.info(f"开始爬取 {len(urls)} 个URL")
        
        # 分批处理
        batch_size = self.concurrent_limit
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i + batch_size]
            
            tasks = [self._crawl_and_parse(url, parse_func) for url in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # 批次间延迟
            if i + batch_size < len(urls):
                await asyncio.sleep(self.request_delay)
        
        await self.close()
        
        # 获取结果
        self.results = self.task_manager.get_results()
        self.logger.info(f"爬取完成，共 {len(self.results)} 条结果")
        
        return self.results
    
    async def _crawl_and_parse(
        self,
        url: str,
        parse_func: Optional[Callable[[str, str], List[Dict]]] = None
    ):
        """爬取并解析"""
        html = await self.crawl_page(url)
        
        if html and parse_func:
            try:
                data = parse_func(url, html)
                if data:
                    for item in data:
                        self.task_manager.results.append(item)
            except Exception as e:
                self.logger.error(f"解析失败: {url}, 错误: {e}")
    
    def save(self, name: Optional[str] = None) -> str:
        """保存结果"""
        if name is None:
            name = self.name
        return self.storage.save(self.results, name, self.output_format)
    
    def save_progress(self):
        """保存进度"""
        self.task_manager.save_state()


class LoginCrawler:
    """需要登录的爬虫"""
    
    def __init__(
        self,
        name: str = "login_crawler",
        headless: bool = True
    ):
        self.name = name
        self.headless = headless
        self.browser = BrowserCrawler(name=f"{name}_browser", headless=headless)
        self.login_manager = None
        self.logger = setup_logger(name)
    
    async def login(
        self,
        login_url: str,
        username: str,
        password: str,
        selectors: Dict[str, str]
    ) -> bool:
        """
        登录
        
        Args:
            login_url: 登录页面
            username: 用户名
            password: 密码
            selectors: 选择器配置
        """
        await self.browser.start()
        
        self.login_manager = LoginManager(self.browser)
        
        success = await self.login_manager.login_with_form(
            login_url=login_url,
            username=username,
            password=password,
            selectors=selectors,
            save_cookies=True
        )
        
        if success:
            self.logger.info("登录成功")
        else:
            self.logger.error("登录失败")
        
        return success
    
    async def crawl_after_login(
        self,
        url: str,
        parse_func: Optional[Callable[[str, str], List[Dict]]] = None
    ) -> Optional[List[Dict]]:
        """登录后爬取"""
        await self.browser.goto(url)
        html = await self.browser.get_content()
        
        if parse_func and html:
            return parse_func(url, html)
        
        return None
    
    async def close(self):
        """关闭"""
        await self.browser.close()


# 使用示例
async def example():
    """使用示例"""
    # 创建增强版爬虫
    crawler = EnhancedCrawler(
        name="example_crawler",
        concurrent_limit=5,
        enable_browser=False
    )
    
    # 添加URL（自动去重）
    urls = [f"https://example.com/page/{i}" for i in range(10)]
    new_count = crawler.add_urls(urls)
    print(f"新增 {new_count} 个URL")
    
    # 定义解析函数
    def parse(url, html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        return [{
            'url': url,
            'title': soup.title.string if soup.title else ''
        }]
    
    # 运行爬虫
    results = await crawler.run(parse_func=parse)
    
    # 保存结果
    crawler.save()
    
    # 获取进度
    print(crawler.get_progress())


if __name__ == "__main__":
    asyncio.run(example())