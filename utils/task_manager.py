"""
任务管理器 - 支持断点续爬、URL去重
"""
import json
import hashlib
import os
import time
from typing import Set, Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import asyncio
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode


@dataclass
class TaskState:
    """任务状态"""
    url: str
    status: str = "pending"  # pending, running, completed, failed
    retry_count: int = 0
    error: str = ""
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at


@dataclass
class CrawlerTask:
    """爬虫任务"""
    name: str
    urls: List[str] = field(default_factory=list)
    completed_urls: List[str] = field(default_factory=list)
    failed_urls: List[str] = field(default_factory=list)
    total: int = 0
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.updated_at:
            self.updated_at = self.created_at
        self.total = len(self.urls)


class URLFilter:
    """URL过滤器 - 去重、规范化"""
    
    def __init__(
        self,
        normalize: bool = True,
        ignore_params: Optional[List[str]] = None,
        ignore_fragments: bool = True
    ):
        """
        初始化
        
        Args:
            normalize: 是否规范化URL
            ignore_params: 忽略的查询参数
            ignore_fragments: 是否忽略URL片段
        """
        self.normalize = normalize
        self.ignore_params = ignore_params or ['utm_source', 'utm_medium', 'utm_campaign', 'ref']
        self.ignore_fragments = ignore_fragments
        self._seen: Set[str] = set()
        self._seen_hashes: Set[str] = set()
    
    def normalize_url(self, url: str) -> str:
        """规范化URL"""
        parsed = urlparse(url)
        
        # 转小写域名
        netloc = parsed.netloc.lower()
        
        # 移除忽略的查询参数
        if parsed.query:
            params = parse_qs(parsed.query, keep_blank_values=True)
            filtered_params = {
                k: v for k, v in params.items()
                if k not in self.ignore_params
            }
            query = urlencode(filtered_params, doseq=True)
        else:
            query = ''
        
        # 移除片段
        fragment = '' if self.ignore_fragments else parsed.fragment
        
        # 重建URL
        normalized = urlunparse((
            parsed.scheme,
            netloc,
            parsed.path,
            parsed.params,
            query,
            fragment
        ))
        
        return normalized
    
    def get_url_hash(self, url: str) -> str:
        """获取URL哈希"""
        normalized = self.normalize_url(url) if self.normalize else url
        return hashlib.md5(normalized.encode()).hexdigest()
    
    def is_seen(self, url: str) -> bool:
        """检查URL是否已见过"""
        url_hash = self.get_url_hash(url)
        return url_hash in self._seen_hashes
    
    def add_url(self, url: str) -> bool:
        """
        添加URL到过滤器
        
        Returns:
            是否为新URL（True=新，False=重复）
        """
        url_hash = self.get_url_hash(url)
        
        if url_hash in self._seen_hashes:
            return False
        
        self._seen_hashes.add(url_hash)
        self._seen.add(self.normalize_url(url) if self.normalize else url)
        return True
    
    def add_urls(self, urls: List[str]) -> List[str]:
        """
        批量添加URL
        
        Returns:
            新增的URL列表
        """
        new_urls = []
        for url in urls:
            if self.add_url(url):
                new_urls.append(url)
        return new_urls
    
    def get_seen_count(self) -> int:
        """获取已见URL数量"""
        return len(self._seen_hashes)
    
    def clear(self):
        """清空过滤器"""
        self._seen.clear()
        self._seen_hashes.clear()
    
    def save(self, filepath: str):
        """保存状态到文件"""
        data = {
            'seen': list(self._seen),
            'seen_hashes': list(self._seen_hashes)
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load(self, filepath: str):
        """从文件加载状态"""
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self._seen = set(data.get('seen', []))
            self._seen_hashes = set(data.get('seen_hashes', []))


class TaskManager:
    """任务管理器 - 支持断点续爬"""
    
    def __init__(
        self,
        name: str,
        data_dir: str = "./tasks",
        auto_save: bool = True,
        save_interval: int = 60
    ):
        """
        初始化
        
        Args:
            name: 任务名称
            data_dir: 数据目录
            auto_save: 自动保存
            save_interval: 保存间隔（秒）
        """
        self.name = name
        self.data_dir = data_dir
        self.auto_save = auto_save
        self.save_interval = save_interval
        
        # 创建数据目录
        os.makedirs(data_dir, exist_ok=True)
        
        # 状态文件
        self.state_file = os.path.join(data_dir, f"{name}_state.json")
        self.url_filter = URLFilter()
        
        # 任务状态
        self.tasks: Dict[str, TaskState] = {}
        self.results: List[Dict] = []
        
        # 加载已有状态
        self._load_state()
        
        # 自动保存任务
        self._save_task = None
    
    def _load_state(self):
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 加载URL过滤器状态
                if 'url_filter' in data:
                    self.url_filter._seen = set(data['url_filter'].get('seen', []))
                    self.url_filter._seen_hashes = set(data['url_filter'].get('seen_hashes', []))
                
                # 加载任务状态
                if 'tasks' in data:
                    for url, state in data['tasks'].items():
                        self.tasks[url] = TaskState(**state)
                
                # 加载结果
                if 'results' in data:
                    self.results = data['results']
                
            except Exception as e:
                print(f"加载状态失败: {e}")
    
    def save_state(self):
        """保存状态"""
        data = {
            'name': self.name,
            'url_filter': {
                'seen': list(self.url_filter._seen),
                'seen_hashes': list(self.url_filter._seen_hashes)
            },
            'tasks': {url: asdict(state) for url, state in self.tasks.items()},
            'results': self.results,
            'updated_at': datetime.now().isoformat()
        }
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_urls(self, urls: List[str]) -> List[str]:
        """添加URL列表，返回新增的URL"""
        new_urls = self.url_filter.add_urls(urls)
        
        for url in new_urls:
            self.tasks[url] = TaskState(url=url, status="pending")
        
        if self.auto_save:
            self.save_state()
        
        return new_urls
    
    def get_pending_urls(self) -> List[str]:
        """获取待处理的URL"""
        return [url for url, state in self.tasks.items() if state.status == "pending"]
    
    def get_running_urls(self) -> List[str]:
        """获取正在处理的URL"""
        return [url for url, state in self.tasks.items() if state.status == "running"]
    
    def get_completed_count(self) -> int:
        """获取已完成数量"""
        return len([s for s in self.tasks.values() if s.status == "completed"])
    
    def get_failed_count(self) -> int:
        """获取失败数量"""
        return len([s for s in self.tasks.values() if s.status == "failed"])
    
    def mark_running(self, url: str):
        """标记为运行中"""
        if url in self.tasks:
            self.tasks[url].status = "running"
            self.tasks[url].updated_at = datetime.now().isoformat()
            if self.auto_save:
                self.save_state()
    
    def mark_completed(self, url: str, result: Optional[Dict] = None):
        """标记为已完成"""
        if url in self.tasks:
            self.tasks[url].status = "completed"
            self.tasks[url].updated_at = datetime.now().isoformat()
        
        if result:
            self.results.append(result)
        
        if self.auto_save:
            self.save_state()
    
    def mark_failed(self, url: str, error: str = ""):
        """标记为失败"""
        if url in self.tasks:
            self.tasks[url].status = "failed"
            self.tasks[url].error = error
            self.tasks[url].retry_count += 1
            self.tasks[url].updated_at = datetime.now().isoformat()
        
        if self.auto_save:
            self.save_state()
    
    def retry_failed(self, max_retries: int = 3) -> List[str]:
        """
        重试失败的任务
        
        Args:
            max_retries: 最大重试次数
        
        Returns:
            可重试的URL列表
        """
        retry_urls = []
        for url, state in self.tasks.items():
            if state.status == "failed" and state.retry_count < max_retries:
                state.status = "pending"
                retry_urls.append(url)
        
        if retry_urls and self.auto_save:
            self.save_state()
        
        return retry_urls
    
    def get_progress(self) -> Dict:
        """获取进度信息"""
        total = len(self.tasks)
        completed = self.get_completed_count()
        failed = self.get_failed_count()
        pending = len(self.get_pending_urls())
        running = len(self.get_running_urls())
        
        return {
            'total': total,
            'completed': completed,
            'failed': failed,
            'pending': pending,
            'running': running,
            'progress': f"{completed}/{total}" if total > 0 else "0/0",
            'percentage': round(completed / total * 100, 2) if total > 0 else 0
        }
    
    def get_results(self) -> List[Dict]:
        """获取所有结果"""
        return self.results
    
    def clear_results(self):
        """清空结果"""
        self.results = []
        if self.auto_save:
            self.save_state()
    
    def reset(self):
        """重置所有状态"""
        self.tasks.clear()
        self.results.clear()
        self.url_filter.clear()
        if os.path.exists(self.state_file):
            os.remove(self.state_file)


# 使用示例
def example():
    """使用示例"""
    # 创建任务管理器
    manager = TaskManager("my_crawler", data_dir="./tasks")
    
    # 添加URL
    urls = [
        "https://example.com/page1",
        "https://example.com/page2",
        "https://example.com/page1?utm_source=test",  # 会被去重
    ]
    new_urls = manager.add_urls(urls)
    print(f"新增URL: {len(new_urls)}个")
    
    # 获取待处理URL
    pending = manager.get_pending_urls()
    print(f"待处理: {len(pending)}个")
    
    # 模拟处理
    for url in pending:
        manager.mark_running(url)
        # ... 执行爬取 ...
        manager.mark_completed(url, {"url": url, "title": "Example"})
    
    # 获取进度
    progress = manager.get_progress()
    print(f"进度: {progress}")
    
    # 获取结果
    results = manager.get_results()
    print(f"结果数量: {len(results)}")


if __name__ == "__main__":
    example()