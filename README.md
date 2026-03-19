# Python爬虫框架

通用爬虫框架，支持同步/异步爬虫、代理池、多种输出格式。

## 功能特性

- ✅ **同步爬虫** - 基于requests，适合简单任务
- ✅ **异步爬虫** - 基于aiohttp，高并发爬取
- ✅ **代理池** - 自动管理代理，支持文件/API导入
- ✅ **多种输出** - JSON/CSV/Excel格式
- ✅ **CSS选择器** - 灵活的页面解析
- ✅ **自动重试** - 请求失败自动重试
- ✅ **User-Agent轮换** - 防止被封

## 项目结构

```
python-crawler/
├── main.py              # CLI入口
├── config.yaml          # 配置文件
├── requirements.txt     # 依赖
├── crawlers/
│   ├── __init__.py
│   ├── base_crawler.py   # 同步爬虫基类
│   ├── simple_crawler.py # 简单同步爬虫
│   └── async_crawler.py  # 异步爬虫
├── utils/
│   ├── __init__.py
│   ├── http_client.py     # 同步HTTP客户端
│   ├── async_http_client.py # 异步HTTP客户端
│   ├── proxy_pool.py      # 代理池
│   ├── parser.py          # HTML解析
│   ├── storage.py         # 数据存储
│   └── logger.py          # 日志
├── logs/                  # 日志目录
└── output/                # 输出目录
```

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 同步爬虫

```bash
# 单个URL
python main.py -u https://example.com

# 多个URL
python main.py --urls https://site1.com https://site2.com

# 指定选择器
python main.py -u https://news.example.com \
  --items-selector "article.news-item" \
  --title-selector "h2.title"

# 输出CSV
python main.py -u https://example.com -o csv
```

### 异步爬虫

```bash
# 异步模式（高并发）
python main.py --async --urls https://site1.com https://site2.com https://site3.com

# 设置并发数
python main.py --async --urls ... --concurrent 20

# 设置请求间隔
python main.py --async --urls ... --delay 0.3
```

### 使用代理池

```bash
# 启用代理池（从config.yaml读取配置）
python main.py --async -u https://example.com --proxy

# 指定代理文件
python main.py --async -u https://example.com --proxy --proxy-file proxies.txt

# 使用代理API
python main.py --async -u https://example.com --proxy --proxy-api "http://api.proxy.com/get?num=20"
```

## 代理池配置

### 配置文件方式

编辑 `config.yaml`:

```yaml
crawler:
  proxy:
    pool:
      enabled: true
      file: "proxies.txt"
      # 或使用API
      # api: "http://api.proxy.com/get?num=20"
      test_url: "https://httpbin.org/ip"
      min_score: 50
```

### 代理文件格式

`proxies.txt`:
```
# 支持格式
192.168.1.1:8080
http://192.168.1.2:8080
socks5://192.168.1.3:1080
```

### 代理池API

```python
from utils import ProxyPool

# 创建代理池
pool = ProxyPool(
    proxies=["http://ip:port", ...],
    proxy_file="proxies.txt",
    proxy_api="http://api.proxy.com/get"
)

# 获取代理
proxy = pool.get()

# 报告结果
pool.report_success(proxy)
pool.report_failure(proxy)

# 检查所有代理
results = pool.check_all()
print(results)  # {"success": 10, "failed": 5, "removed": 2}

# 统计信息
stats = pool.get_stats()
print(stats)  # {"total": 15, "valid": 13, "avg_score": 85.5}
```

## 代码示例

### 自定义同步爬虫

```python
from crawlers import BaseCrawler
from typing import List, Dict

class MyCrawler(BaseCrawler):
    def __init__(self):
        super().__init__(name="my_crawler")
    
    def start_urls(self) -> List[str]:
        return ["https://example.com/page1", "https://example.com/page2"]
    
    def parse(self, url: str, html: str) -> List[Dict]:
        soup = self.parser.parse(html)
        results = []
        
        for item in soup.select("article"):
            results.append({
                "title": item.select_one("h2").text,
                "link": item.select_one("a")["href"]
            })
        
        return results

# 运行
crawler = MyCrawler()
results = crawler.run()
crawler.save()
crawler.close()
```

### 自定义异步爬虫

```python
from crawlers import AsyncCrawler
from typing import List, Dict
import asyncio

class MyAsyncCrawler(AsyncCrawler):
    def __init__(self, urls: List[str]):
        super().__init__(name="my_async_crawler", concurrent_limit=10)
        self.urls = urls
    
    def start_urls(self) -> List[str]:
        return self.urls
    
    async def parse(self, url: str, html: str) -> List[Dict]:
        soup = self.parser.parse(html)
        results = []
        
        for item in soup.select("div.item"):
            results.append({
                "url": url,
                "title": self.parser.extract_text(item.select_one("h3"))
            })
        
        return results

# 运行
async def main():
    crawler = MyAsyncCrawler(["https://example.com"] * 100)
    results = await crawler.run()
    crawler.save()

asyncio.run(main())
```

## 输出格式

支持三种输出格式：

- `json` - JSON格式（默认）
- `csv` - CSV表格
- `excel` - Excel表格（需要pandas）

## License

MIT