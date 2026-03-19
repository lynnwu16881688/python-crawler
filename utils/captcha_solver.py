"""
验证码识别模块
支持多种验证码类型的识别
"""
import base64
import hashlib
import os
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import asyncio


class CaptchaSolver(ABC):
    """验证码识别基类"""
    
    @abstractmethod
    async def solve(self, image_data: bytes, **kwargs) -> str:
        """识别验证码"""
        pass
    
    @abstractmethod
    async def get_balance(self) -> float:
        """获取账户余额"""
        pass


class MockCaptchaSolver(CaptchaSolver):
    """模拟验证码识别（用于测试）"""
    
    def __init__(self, auto_pass: bool = True):
        self.auto_pass = auto_pass
    
    async def solve(self, image_data: bytes, **kwargs) -> str:
        """模拟识别"""
        if self.auto_pass:
            return "mock_answer"
        # 返回空，等待人工处理
        return ""
    
    async def get_balance(self) -> float:
        return 999.0


class YesCaptchaSolver(CaptchaSolver):
    """YesCaptcha验证码识别服务"""
    
    def __init__(self, api_key: str):
        """
        初始化
        
        Args:
            api_key: API密钥
        """
        self.api_key = api_key
        self.base_url = "https://api.yescaptcha.com"
    
    async def solve(self, image_data: bytes, **kwargs) -> str:
        """
        识别图片验证码
        
        Args:
            image_data: 图片二进制数据
            **kwargs: 额外参数
                - captcha_type: 验证码类型 (recaptcha, hcaptcha, image)
                - site_key: reCAPTCHA/hCaptcha site key
                - page_url: 页面URL
        """
        import aiohttp
        
        captcha_type = kwargs.get('captcha_type', 'image')
        
        async with aiohttp.ClientSession() as session:
            if captcha_type == 'image':
                # 图片验证码
                image_base64 = base64.b64encode(image_data).decode()
                
                async with session.post(
                    f"{self.base_url}/api/createTask",
                    json={
                        "clientKey": self.api_key,
                        "task": {
                            "type": "ImageToTextTask",
                            "body": image_base64
                        }
                    }
                ) as resp:
                    result = await resp.json()
                    task_id = result.get('taskId')
                    
                    if not task_id:
                        return ""
                    
                    # 等待结果
                    for _ in range(30):
                        await asyncio.sleep(2)
                        async with session.get(
                            f"{self.base_url}/api/getTaskResult",
                            json={
                                "clientKey": self.api_key,
                                "taskId": task_id
                            }
                        ) as result_resp:
                            result = await result_resp.json()
                            if result.get('status') == 'ready':
                                return result.get('solution', {}).get('text', '')
            
            elif captcha_type in ['recaptcha', 'hcaptcha']:
                # reCAPTCHA/hCaptcha
                site_key = kwargs.get('site_key')
                page_url = kwargs.get('page_url')
                
                task_type = "RecaptchaV2TaskProxyless" if captcha_type == 'recaptcha' else "HCaptchaTaskProxyless"
                
                async with session.post(
                    f"{self.base_url}/api/createTask",
                    json={
                        "clientKey": self.api_key,
                        "task": {
                            "type": task_type,
                            "websiteURL": page_url,
                            "websiteKey": site_key
                        }
                    }
                ) as resp:
                    result = await resp.json()
                    task_id = result.get('taskId')
                    
                    if not task_id:
                        return ""
                    
                    # 等待结果
                    for _ in range(60):
                        await asyncio.sleep(3)
                        async with session.get(
                            f"{self.base_url}/api/getTaskResult",
                            json={
                                "clientKey": self.api_key,
                                "taskId": task_id
                            }
                        ) as result_resp:
                            result = await result_resp.json()
                            if result.get('status') == 'ready':
                                return result.get('solution', {}).get('gRecaptchaResponse', '')
        
        return ""
    
    async def get_balance(self) -> float:
        """获取余额"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/getBalance",
                json={"clientKey": self.api_key}
            ) as resp:
                result = await resp.json()
                return result.get('balance', 0)


class TwoCaptchaSolver(CaptchaSolver):
    """2Captcha验证码识别服务"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://2captcha.com"
    
    async def solve(self, image_data: bytes, **kwargs) -> str:
        """识别验证码"""
        import aiohttp
        
        image_base64 = base64.b64encode(image_data).decode()
        
        async with aiohttp.ClientSession() as session:
            # 提交任务
            async with session.post(
                f"{self.base_url}/in.php",
                data={
                    "key": self.api_key,
                    "method": "base64",
                    "body": image_base64,
                    "json": 1
                }
            ) as resp:
                result = await resp.json()
                task_id = result.get('request')
                
                if not task_id:
                    return ""
            
            # 等待结果
            for _ in range(30):
                await asyncio.sleep(3)
                async with session.get(
                    f"{self.base_url}/res.php",
                    params={
                        "key": self.api_key,
                        "action": "get",
                        "id": task_id,
                        "json": 1
                    }
                ) as resp:
                    result = await resp.json()
                    if result.get('status') == 1:
                        return result.get('request', '')
        
        return ""
    
    async def get_balance(self) -> float:
        """获取余额"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/res.php",
                params={
                    "key": self.api_key,
                    "action": "getbalance",
                    "json": 1
                }
            ) as resp:
                result = await resp.json()
                return result.get('request', 0)


class CaptchaManager:
    """验证码管理器"""
    
    def __init__(self, solver: Optional[CaptchaSolver] = None):
        """
        初始化
        
        Args:
            solver: 验证码识别器实例
        """
        self.solver = solver or MockCaptchaSolver()
    
    def set_solver(self, solver: CaptchaSolver):
        """设置识别器"""
        self.solver = solver
    
    async def solve_image_captcha(self, image_path: str = None, image_data: bytes = None) -> str:
        """识别图片验证码"""
        if image_path and os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                image_data = f.read()
        
        if not image_data:
            return ""
        
        return await self.solver.solve(image_data, captcha_type='image')
    
    async def solve_recaptcha(
        self,
        site_key: str,
        page_url: str
    ) -> str:
        """识别reCAPTCHA v2"""
        return await self.solver.solve(
            b'',
            captcha_type='recaptcha',
            site_key=site_key,
            page_url=page_url
        )
    
    async def solve_hcaptcha(
        self,
        site_key: str,
        page_url: str
    ) -> str:
        """识别hCaptcha"""
        return await self.solver.solve(
            b'',
            captcha_type='hcaptcha',
            site_key=site_key,
            page_url=page_url
        )
    
    async def get_balance(self) -> float:
        """获取账户余额"""
        return await self.solver.get_balance()


def create_captcha_solver(
    provider: str = "mock",
    api_key: str = None
) -> CaptchaSolver:
    """
    创建验证码识别器
    
    Args:
        provider: 服务商 (mock, yescaptcha, 2captcha)
        api_key: API密钥
    
    Returns:
        验证码识别器实例
    """
    if provider == "yescaptcha":
        if not api_key:
            api_key = os.environ.get("YESCAPTCHA_API_KEY", "")
        return YesCaptchaSolver(api_key) if api_key else MockCaptchaSolver()
    
    elif provider == "2captcha":
        if not api_key:
            api_key = os.environ.get("TWOCAPTCHA_API_KEY", "")
        return TwoCaptchaSolver(api_key) if api_key else MockCaptchaSolver()
    
    return MockCaptchaSolver()


# 使用示例
async def example():
    """使用示例"""
    # 创建验证码管理器
    manager = CaptchaManager()
    
    # 使用第三方服务（需要API密钥）
    # solver = create_captcha_solver("yescaptcha", "your_api_key")
    # manager.set_solver(solver)
    
    # 获取余额
    balance = await manager.get_balance()
    print(f"账户余额: {balance}")
    
    # 识别图片验证码
    # result = await manager.solve_image_captcha("captcha.png")
    # print(f"识别结果: {result}")


if __name__ == "__main__":
    asyncio.run(example())