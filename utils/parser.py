"""
HTML解析工具
支持BeautifulSoup和lxml
"""
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from lxml import etree


class Parser:
    """HTML解析器"""
    
    def __init__(self, parser: str = "lxml"):
        self.parser = parser
    
    def parse(self, html: str) -> BeautifulSoup:
        """解析HTML"""
        return BeautifulSoup(html, self.parser)
    
    def select(self, soup: BeautifulSoup, selector: str) -> List:
        """CSS选择器"""
        return soup.select(selector)
    
    def select_one(self, soup: BeautifulSoup, selector: str) -> Optional[Any]:
        """CSS选择器（单个）"""
        return soup.select_one(selector)
    
    def xpath(self, html: str, xpath_expr: str) -> List:
        """XPath选择"""
        tree = etree.HTML(html)
        return tree.xpath(xpath_expr)
    
    def extract_text(self, element) -> str:
        """提取文本"""
        if element:
            return element.get_text(strip=True)
        return ""
    
    def extract_attr(self, element, attr: str) -> str:
        """提取属性"""
        if element:
            return element.get(attr, "")
        return ""
    
    def extract_links(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, str]]:
        """提取所有链接"""
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if base_url and not href.startswith('http'):
                href = base_url.rstrip('/') + '/' + href.lstrip('/')
            links.append({
                'text': a.get_text(strip=True),
                'href': href
            })
        return links
    
    def extract_images(self, soup: BeautifulSoup, base_url: str = "") -> List[Dict[str, str]]:
        """提取所有图片"""
        images = []
        for img in soup.find_all('img', src=True):
            src = img['src']
            if base_url and not src.startswith('http'):
                src = base_url.rstrip('/') + '/' + src.lstrip('/')
            images.append({
                'alt': img.get('alt', ''),
                'src': src
            })
        return images