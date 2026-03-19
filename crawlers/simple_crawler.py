"""
简单爬虫示例
爬取新闻网站示例
"""
from typing import List, Dict
from crawlers.base_crawler import BaseCrawler


class SimpleCrawler(BaseCrawler):
    """简单爬虫示例"""
    
    def __init__(self, urls: List[str], selectors: Dict[str, str]):
        """
        初始化
        
        Args:
            urls: 要爬取的URL列表
            selectors: CSS选择器配置
                {
                    'items': 'div.news-item',  # 列表项选择器
                    'title': 'h2.title',       # 标题选择器
                    'link': 'a',               # 链接选择器
                    'summary': 'p.summary'     # 摘要选择器
                }
        """
        super().__init__(name="simple_crawler")
        self.urls = urls
        self.selectors = selectors
    
    def start_urls(self) -> List[str]:
        return self.urls
    
    def parse(self, url: str, html: str) -> List[Dict]:
        soup = self.parser.parse(html)
        results = []
        
        # 获取列表项
        items_selector = self.selectors.get('items', 'body')
        items = self.parser.select(soup, items_selector)
        
        for item in items:
            data = {'source_url': url}
            
            # 提取各字段
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
if __name__ == "__main__":
    # 示例配置
    crawler = SimpleCrawler(
        urls=[
            "https://example.com/news",
        ],
        selectors={
            'items': 'article.news-item',
            'title': 'h2',
            'link': 'a',
            'summary': 'p',
            'date': 'span.date'
        }
    )
    
    # 运行爬虫
    results = crawler.run()
    
    # 保存结果
    filename = crawler.save()
    print(f"数据已保存到: {filename}")
    
    # 关闭
    crawler.close()