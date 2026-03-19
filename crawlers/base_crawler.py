"""
爬虫基类
"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import HttpClient, setup_logger, Parser, Storage


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(
        self,
        name: str = "base_crawler",
        timeout: int = 30,
        retry_times: int = 3,
        output_format: str = "json"
    ):
        self.name = name
        self.http = HttpClient(timeout=timeout, retry_times=retry_times)
        self.parser = Parser()
        self.storage = Storage()
        self.output_format = output_format
        self.logger = setup_logger(name)
        self.results: List[Dict] = []
    
    @abstractmethod
    def start_urls(self) -> List[str]:
        """起始URL列表"""
        pass
    
    @abstractmethod
    def parse(self, url: str, html: str) -> List[Dict]:
        """解析页面"""
        pass
    
    def before_request(self, url: str) -> Optional[Dict]:
        """请求前的钩子，可返回额外参数"""
        return None
    
    def after_parse(self, data: List[Dict]) -> List[Dict]:
        """解析后的钩子，可处理数据"""
        return data
    
    def run(self) -> List[Dict]:
        """运行爬虫"""
        self.logger.info(f"爬虫 {self.name} 开始运行...")
        
        urls = self.start_urls()
        self.logger.info(f"共 {len(urls)} 个URL待爬取")
        
        for i, url in enumerate(urls, 1):
            self.logger.info(f"正在爬取 [{i}/{len(urls)}]: {url}")
            
            # 请求前钩子
            extra = self.before_request(url)
            
            # 发送请求
            response = self.http.get(url)
            if response is None:
                self.logger.warning(f"请求失败: {url}")
                continue
            
            # 解析页面
            data = self.parse(url, response.text)
            
            # 解析后钩子
            data = self.after_parse(data)
            
            self.results.extend(data)
            self.logger.info(f"从 {url} 提取了 {len(data)} 条数据")
        
        self.logger.info(f"爬虫 {self.name} 完成，共获取 {len(self.results)} 条数据")
        
        return self.results
    
    def save(self, name: Optional[str] = None) -> str:
        """保存结果"""
        if name is None:
            name = self.name
        return self.storage.save(self.results, name, self.output_format)
    
    def close(self):
        """关闭资源"""
        self.http.close()