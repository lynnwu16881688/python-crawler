# Python爬虫框架

通用爬虫框架，支持同步/异步爬虫、代理池、JavaScript渲染、登录认证、验证码识别。

## 功能特性

### 核心功能
- ✅ **同步爬虫** - 基于requests，适合简单任务
- ✅ **异步爬虫** - 基于aiohttp，高并发爬取
- ✅ **代理池** - 自动管理代理，支持文件/API导入
- ✅ **多种输出** - JSON/CSV/Excel格式
- ✅ **CSS选择器** - 灵活的页面解析
- ✅ **自动重试** - 请求失败自动重试
- ✅ **User-Agent轮换** - 防止被封

### 高级功能 🆕
- ✅ **JavaScript渲染** - 基于Playwright，支持动态页面
- ✅ **登录认证** - 支持表单登录、Cookie管理
- ✅ **验证码识别** - 支持图片验证码、reCAPTCHA、hCaptcha
- ✅ **断点续爬** - 任务中断后自动恢复
- ✅ **URL去重** - 自动去重，支持规范化

## 项目结构

```
python-crawler/
├── main.py                 # CLI入口
├── config.yaml             # 配置文件
├── requirements.txt        # 依赖
├── crawlers/
│   ├── base_crawler.py     # 同步爬虫基类
│   ├── simple_crawler.py   # 简单同步爬虫
│   ├── async_crawler.py    # 异步爬虫
│   └── enhanced_crawler.py # 增强版爬虫（集成所有功能）
└── utils/
    ├── http_client.py      # 同步HTTP客户端
    ├── async_http_client.py# 异步HTTP客户端
    ├── browser_crawler.py  # 浏览器爬虫（JS渲染）🆕
    ├── proxy_pool.py       # 代理池
    ├── captcha_solver.py   # 验证码识别 🆕
    ├── task_manager.py     # 任务管理（断点续爬）🆕
    ├── parser.py           # HTML解析
    ├── storage.py          # 数据存储
    └── logger.py           # 日志
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt

# 如需JavaScript渲染，还需安装Playwright
playwright install chromium
```

### 基础使用

```bash
# 同步爬取
python main.py -u https://example.com

# 异步并发爬取
python main.py --async --urls https://site1.com https://site2.com --concurrent 10

# 使用代理池
python main.py --async -u https://example.com --proxy
```

## 高级用法

### 1. JavaScript动态页面

```python
from utils import BrowserCrawler
import asyncio

async def crawl_dynamic_page():
    async with BrowserCrawler(headless=True) as crawler:
        # 访问动态页面
        await crawler.goto('https://example.com')
        
        # 等待元素加载
        await crawler.wait_for_selector('article')
        
        # 获取内容
        html = await crawler.get_content()
        
        # 滚动加载更多
        await crawler.scroll_to_bottom()
        
        # 截图
        await crawler.screenshot('page.png')

asyncio.run(crawl_dynamic_page())
```

### 2. 需要登录的网站

```python
from crawlers import LoginCrawler
import asyncio

async def crawl_after_login():
    crawler = LoginCrawler(name="my_crawler", headless=True)
    
    # 登录
    success = await crawler.login(
        login_url="https://example.com/login",
        username="your_username",
        password="your_password",
        selectors={
            'username': 'input[name="username"]',
            'password': 'input[name="password"]',
            'submit': 'button[type="submit"]',
            'success_check': '.user-profile'  # 登录成功后的元素
        }
    )
    
    if success:
        # 爬取需要登录的页面
        results = await crawler.crawl_after_login(
            "https://example.com/dashboard",
            parse_func=lambda url, html: [{"url": url, "content": html}]
        )
    
    await crawler.close()

asyncio.run(crawl_after_login())
```

### 3. 验证码识别

```python
from utils import CaptchaManager, create_captcha_solver
import asyncio

async def handle_captcha():
    # 使用第三方服务
    solver = create_captcha_solver("yescaptcha", "your_api_key")
    manager = CaptchaManager(solver)
    
    # 检查余额
    balance = await manager.get_balance()
    print(f"余额: {balance}")
    
    # 识别图片验证码
    result = await manager.solve_image_captcha("captcha.png")
    print(f"验证码: {result}")
    
    # 识别reCAPTCHA
    token = await manager.solve_recaptcha(
        site_key="6Lc...",
        page_url="https://example.com"
    )

asyncio.run(handle_captcha())
```

### 4. 断点续爬

```python
from crawlers import EnhancedCrawler
import asyncio

async def crawl_with_resume():
    crawler = EnhancedCrawler(
        name="my_task",
        data_dir="./tasks",
        concurrent_limit=10
    )
    
    # 添加URL（自动去重）
    urls = [f"https://example.com/page/{i}" for i in range(1000)]
    new_count = crawler.add_urls(urls)
    
    # 运行爬虫（支持中断恢复）
    results = await crawler.run(parse_func=my_parse_func)
    
    # 查看进度
    progress = crawler.get_progress()
    print(f"进度: {progress['progress']} ({progress['percentage']}%)")
    
    # 保存结果
    crawler.save()

asyncio.run(crawl_with_resume())
```

### 5. 完整示例（集成所有功能）

```python
from crawlers import EnhancedCrawler
from utils import ProxyPool, BrowserCrawler
import asyncio

async def full_example():
    # 创建代理池
    proxy_pool = ProxyPool(
        proxy_file="proxies.txt",
        test_url="https://httpbin.org/ip"
    )
    
    # 创建增强版爬虫
    crawler = EnhancedCrawler(
        name="advanced_crawler",
        concurrent_limit=20,
        request_delay=0.3,
        use_proxy=True,
        proxy_pool=proxy_pool,
        enable_browser=False,  # 按需开启
        retry_times=3
    )
    
    # 添加URL
    urls = ["https://example.com/page1", "https://example.com/page2"]
    crawler.add_urls(urls)
    
    # 解析函数
    def parse(url, html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')
        items = soup.select('article')
        return [{
            'url': url,
            'title': item.select_one('h2').text,
            'content': item.select_one('p').text
        } for item in items]
    
    # 运行
    results = await crawler.run(parse_func=parse)
    crawler.save()

asyncio.run(full_example())
```

## 配置说明

编辑 `config.yaml`:

```yaml
crawler:
  async:
    concurrent_limit: 10
    request_delay: 0.5
  
  proxy:
    pool:
      enabled: true
      file: "proxies.txt"
      api: "http://api.proxy.com/get"
  
  browser:
    enabled: false
    headless: true
  
  captcha:
    provider: "yescaptcha"  # yescaptcha, 2captcha
    api_key: ""  # 或设置环境变量

output:
  dir: "./output"
  format: "json"
```

## 依赖说明

### 核心依赖
- requests - HTTP请求
- aiohttp - 异步HTTP请求
- beautifulsoup4 - HTML解析
- lxml - 解析器
- fake-useragent - UA轮换

### 可选依赖
- playwright - JavaScript渲染
- pandas - Excel输出

## 适用场景

| 场景 | 推荐方案 |
|------|----------|
| 静态页面 | 异步爬虫 |
| 动态页面 | 浏览器爬虫 |
| 需要登录 | LoginCrawler |
| 大规模采集 | EnhancedCrawler + 断点续爬 |
| 反爬严格 | 代理池 + 验证码识别 |

## 注意事项

1. 遵守网站的robots.txt规则
2. 设置合理的请求间隔
3. 使用代理池分散请求
4. 对于验证码，建议使用第三方识别服务

## License

MIT