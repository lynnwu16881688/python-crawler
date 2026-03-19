"""
浏览器爬虫 - 支持JavaScript渲染
基于Playwright，支持动态页面、登录、验证码处理
"""
import asyncio
import random
import time
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext


class BrowserCrawler:
    """浏览器爬虫类 - 支持JavaScript渲染"""
    
    def __init__(
        self,
        name: str = "browser_crawler",
        headless: bool = True,
        timeout: int = 30000,
        slow_mo: int = 0,
        user_agent: Optional[str] = None,
        proxy: Optional[str] = None,
        cookies: Optional[List[Dict]] = None
    ):
        """
        初始化
        
        Args:
            name: 爬虫名称
            headless: 无头模式
            timeout: 超时时间（毫秒）
            slow_mo: 操作延迟（毫秒）
            user_agent: 自定义UA
            proxy: 代理地址
            cookies: Cookie列表
        """
        self.name = name
        self.headless = headless
        self.timeout = timeout
        self.slow_mo = slow_mo
        self.user_agent = user_agent
        self.proxy = proxy
        self.cookies = cookies
        
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
    
    async def start(self):
        """启动浏览器"""
        self._playwright = await async_playwright().start()
        
        # 浏览器启动参数
        launch_args = {
            'headless': self.headless,
            'slow_mo': self.slow_mo,
        }
        
        if self.proxy:
            launch_args['proxy'] = {'server': self.proxy}
        
        self._browser = await self._playwright.chromium.launch(**launch_args)
        
        # 创建上下文
        context_args = {}
        if self.user_agent:
            context_args['user_agent'] = self.user_agent
        
        self._context = await self._browser.new_context(**context_args)
        
        # 设置默认超时
        self._context.set_default_timeout(self.timeout)
        
        # 添加Cookie
        if self.cookies:
            await self._context.add_cookies(self.cookies)
        
        # 创建页面
        self._page = await self._context.new_page()
        
        return self
    
    async def close(self):
        """关闭浏览器"""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def goto(
        self,
        url: str,
        wait_until: str = "networkidle",
        timeout: Optional[int] = None
    ) -> Page:
        """
        访问页面
        
        Args:
            url: 目标URL
            wait_until: 等待策略 (load, domcontentloaded, networkidle)
            timeout: 超时时间
        """
        if not self._page:
            await self.start()
        
        await self._page.goto(url, wait_until=wait_until, timeout=timeout)
        return self._page
    
    async def wait_for_selector(
        self,
        selector: str,
        timeout: Optional[int] = None
    ):
        """等待元素出现"""
        await self._page.wait_for_selector(selector, timeout=timeout)
    
    async def wait_for_timeout(self, ms: int):
        """等待指定时间"""
        await self._page.wait_for_timeout(ms)
    
    async def click(self, selector: str, delay: int = 0):
        """点击元素"""
        await self._page.click(selector, delay=delay)
    
    async def fill(self, selector: str, value: str):
        """填充输入框"""
        await self._page.fill(selector, value)
    
    async def type_text(self, selector: str, text: str, delay: int = 50):
        """模拟打字"""
        await self._page.type(selector, text, delay=delay)
    
    async def screenshot(self, path: str, full_page: bool = False):
        """截图"""
        await self._page.screenshot(path=path, full_page=full_page)
    
    async def get_content(self) -> str:
        """获取页面HTML"""
        return await self._page.content()
    
    async def get_text(self, selector: str) -> str:
        """获取元素文本"""
        element = await self._page.query_selector(selector)
        if element:
            return await element.inner_text()
        return ""
    
    async def get_attribute(self, selector: str, attr: str) -> Optional[str]:
        """获取元素属性"""
        element = await self._page.query_selector(selector)
        if element:
            return await element.get_attribute(attr)
        return None
    
    async def query_selector_all(self, selector: str) -> List:
        """查询所有匹配元素"""
        return await self._page.query_selector_all(selector)
    
    async def evaluate(self, script: str) -> Any:
        """执行JavaScript"""
        return await self._page.evaluate(script)
    
    async def scroll_to_bottom(self, delay: int = 500):
        """滚动到底部（用于加载更多内容）"""
        await self.evaluate("""
            async () => {
                const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
                const scrollHeight = document.documentElement.scrollHeight;
                for (let i = 0; i < scrollHeight; i += 500) {
                    window.scrollTo(0, i);
                    await delay(""" + str(delay) + """);
                }
            }
        """)
    
    async def get_cookies(self) -> List[Dict]:
        """获取当前Cookie"""
        return await self._context.cookies()
    
    async def set_cookies(self, cookies: List[Dict]):
        """设置Cookie"""
        await self._context.add_cookies(cookies)
    
    async def save_cookies(self, filepath: str):
        """保存Cookie到文件"""
        import json
        cookies = await self.get_cookies()
        with open(filepath, 'w') as f:
            json.dump(cookies, f)
    
    async def load_cookies(self, filepath: str):
        """从文件加载Cookie"""
        import json
        import os
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                cookies = json.load(f)
            await self.set_cookies(cookies)
    
    async def login_form(
        self,
        url: str,
        username_selector: str,
        password_selector: str,
        submit_selector: str,
        username: str,
        password: str,
        success_check: Optional[str] = None
    ) -> bool:
        """
        表单登录
        
        Args:
            url: 登录页面URL
            username_selector: 用户名输入框选择器
            password_selector: 密码输入框选择器
            submit_selector: 提交按钮选择器
            username: 用户名
            password: 密码
            success_check: 登录成功检测选择器
        
        Returns:
            是否登录成功
        """
        await self.goto(url)
        
        # 填充用户名和密码
        await self.fill(username_selector, username)
        await self.fill(password_selector, password)
        
        # 点击登录
        await self.click(submit_selector)
        
        # 等待跳转或成功标志
        if success_check:
            try:
                await self.wait_for_selector(success_check, timeout=10000)
                return True
            except:
                return False
        
        # 等待URL变化
        await self.wait_for_timeout(2000)
        return True
    
    async def handle_captcha_click(self, selector: str, delay: int = 1000):
        """
        处理点击式验证码（如滑块验证、点选验证）
        需要人工或第三方服务处理
        """
        # 这里可以集成第三方验证码识别服务
        # 目前只是等待人工处理
        print(f"请手动处理验证码，选择器: {selector}")
        await self.wait_for_timeout(delay)
    
    async def __aenter__(self):
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class LoginManager:
    """登录管理器 - 支持多种登录方式"""
    
    def __init__(self, browser_crawler: BrowserCrawler):
        self.crawler = browser_crawler
        self.logged_in = False
        self.cookies_file = None
    
    async def login_with_form(
        self,
        login_url: str,
        username: str,
        password: str,
        selectors: Dict[str, str],
        save_cookies: bool = True
    ) -> bool:
        """
        表单登录
        
        Args:
            login_url: 登录页面
            username: 用户名
            password: 密码
            selectors: 选择器配置
            save_cookies: 是否保存Cookie
        """
        success = await self.crawler.login_form(
            url=login_url,
            username_selector=selectors.get('username', 'input[name="username"]'),
            password_selector=selectors.get('password', 'input[name="password"]'),
            submit_selector=selectors.get('submit', 'button[type="submit"]'),
            username=username,
            password=password,
            success_check=selectors.get('success_check')
        )
        
        if success:
            self.logged_in = True
            if save_cookies:
                await self.crawler.save_cookies(self.cookies_file or 'cookies.json')
        
        return success
    
    async def login_with_cookies(self, cookies_file: str) -> bool:
        """使用Cookie登录"""
        await self.crawler.load_cookies(cookies_file)
        self.logged_in = True
        self.cookies_file = cookies_file
        return True
    
    async def check_login_status(self, check_selector: str) -> bool:
        """检查登录状态"""
        try:
            await self.crawler.wait_for_selector(check_selector, timeout=5000)
            return True
        except:
            return False


# 使用示例
async def example():
    """使用示例"""
    async with BrowserCrawler(headless=True) as crawler:
        # 访问动态页面
        await crawler.goto('https://example.com')
        
        # 等待元素
        await crawler.wait_for_selector('article')
        
        # 获取内容
        content = await crawler.get_content()
        print(f"页面内容长度: {len(content)}")
        
        # 截图
        await crawler.screenshot('screenshot.png')
        
        # 滚动加载更多
        await crawler.scroll_to_bottom()


if __name__ == "__main__":
    asyncio.run(example())