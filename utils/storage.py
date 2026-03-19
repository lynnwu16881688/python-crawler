"""
数据存储工具
支持JSON、CSV、Excel格式
"""
import json
import csv
import os
from typing import List, Dict, Any
from datetime import datetime


class Storage:
    """数据存储类"""
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def _get_filename(self, name: str, ext: str) -> str:
        """生成文件名"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return os.path.join(self.output_dir, f"{name}_{timestamp}.{ext}")
    
    def save_json(self, data: Any, name: str = "data") -> str:
        """保存JSON文件"""
        filename = self._get_filename(name, "json")
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filename
    
    def save_csv(self, data: List[Dict], name: str = "data") -> str:
        """保存CSV文件"""
        if not data:
            return ""
        
        filename = self._get_filename(name, "csv")
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        return filename
    
    def save_excel(self, data: List[Dict], name: str = "data") -> str:
        """保存Excel文件"""
        try:
            import pandas as pd
            
            if not data:
                return ""
            
            filename = self._get_filename(name, "xlsx")
            df = pd.DataFrame(data)
            df.to_excel(filename, index=False, engine='openpyxl')
            return filename
        except ImportError:
            print("请安装pandas和openpyxl: pip install pandas openpyxl")
            return self.save_csv(data, name)
    
    def save(self, data: Any, name: str = "data", format: str = "json") -> str:
        """通用保存方法"""
        format = format.lower()
        if format == "json":
            return self.save_json(data, name)
        elif format == "csv":
            return self.save_csv(data, name)
        elif format == "excel":
            return self.save_excel(data, name)
        else:
            return self.save_json(data, name)