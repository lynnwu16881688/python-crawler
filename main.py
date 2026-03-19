#!/usr/bin/env python3
"""
Python爬虫框架
通用爬虫框架，支持同步/异步爬虫、代理池、多种输出格式
"""
import argparse
import asyncio
import yaml
from typing import Optional
from crawlers import SimpleCrawler, AsyncSimpleCrawler
from utils import setup_logger, ProxyPool


def load_config(config_file: str = "config.yaml") -> dict:
    """加载配置文件"""
    with open(config_file, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_proxy_pool(config: dict) -> Optional[ProxyPool]:
    """根据配置创建代理池"""
    proxy_config = config.get('crawler', {}).get('proxy', {})
    pool_config = proxy_config.get('pool', {})
    
    if not pool_config.get('enabled', False):
        return None
    
    return ProxyPool(
        proxy_file=pool_config.get('file') if pool_config.get('file') else None,
        proxy_api=pool_config.get('api') if pool_config.get('api') else None,
        test_url=pool_config.get('test_url', 'https://httpbin.org/ip'),
        min_score=pool_config.get('min_score', 50),
        check_interval=pool_config.get('check_interval', 300)
    )


def run_sync(args, config: dict, logger):
    """运行同步爬虫"""
    urls = args.urls or ([args.url] if args.url else [])
    if not urls:
        logger.error("请提供要爬取的URL")
        return
    
    selectors = {
        'items': args.items_selector,
        'title': args.title_selector,
    }
    
    proxy_pool = create_proxy_pool(config) if args.proxy else None
    
    crawler = SimpleCrawler(
        urls=urls,
        selectors=selectors,
        proxy=proxy_pool.get() if proxy_pool else None
    )
    crawler.output_format = args.output
    
    results = crawler.run()
    
    if results:
        filename = crawler.save()
        logger.info(f"数据已保存到: {filename}")
    else:
        logger.warning("未获取到数据")
    
    crawler.close()


async def run_async(args, config: dict, logger):
    """运行异步爬虫"""
    urls = args.urls or ([args.url] if args.url else [])
    if not urls:
        logger.error("请提供要爬取的URL")
        return
    
    selectors = {
        'items': args.items_selector,
        'title': args.title_selector,
    }
    
    async_config = config.get('crawler', {}).get('async', {})
    proxy_pool = create_proxy_pool(config) if args.proxy else None
    
    crawler = AsyncSimpleCrawler(
        urls=urls,
        selectors=selectors,
        concurrent_limit=async_config.get('concurrent_limit', args.concurrent),
        request_delay=async_config.get('request_delay', args.delay),
        proxy_pool=proxy_pool
    )
    crawler.output_format = args.output
    
    results = await crawler.run()
    
    if results:
        filename = crawler.save()
        logger.info(f"数据已保存到: {filename}")
    else:
        logger.warning("未获取到数据")


def main():
    parser = argparse.ArgumentParser(
        description='Python爬虫框架 - 支持同步/异步爬虫、代理池',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 同步爬取单个页面
  python main.py -u https://example.com
  
  # 异步并发爬取多个页面
  python main.py --async --urls https://site1.com https://site2.com --concurrent 5
  
  # 使用代理池
  python main.py --async -u https://example.com --proxy
  
  # 指定选择器
  python main.py -u https://news.example.com --items-selector "article" --title-selector "h2"
        """
    )
    
    # 基本参数
    parser.add_argument('-c', '--config', default='config.yaml', help='配置文件路径')
    parser.add_argument('-u', '--url', help='要爬取的URL')
    parser.add_argument('-o', '--output', default='json', choices=['json', 'csv', 'excel'], help='输出格式')
    
    # URL参数
    parser.add_argument('--urls', nargs='+', help='多个URL')
    
    # 选择器参数
    parser.add_argument('--items-selector', default='body', help='列表项选择器')
    parser.add_argument('--title-selector', default='h1', help='标题选择器')
    
    # 异步参数
    parser.add_argument('--async', dest='async_mode', action='store_true', help='使用异步模式')
    parser.add_argument('--concurrent', type=int, default=10, help='并发数（异步模式）')
    parser.add_argument('--delay', type=float, default=0.5, help='请求间隔秒数（异步模式）')
    
    # 代理参数
    parser.add_argument('--proxy', action='store_true', help='启用代理池')
    parser.add_argument('--proxy-file', help='代理文件路径')
    parser.add_argument('--proxy-api', help='代理API地址')
    
    args = parser.parse_args()
    
    # 加载配置
    config = load_config(args.config)
    
    # 设置日志
    logger = setup_logger(
        name="main",
        level=config.get('logging', {}).get('level', 'INFO'),
        log_dir=config.get('logging', {}).get('dir')
    )
    
    # 运行爬虫
    if args.async_mode:
        asyncio.run(run_async(args, config, logger))
    else:
        run_sync(args, config, logger)


if __name__ == "__main__":
    main()