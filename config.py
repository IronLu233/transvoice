import os
from typing import Optional


def get_api_key() -> Optional[str]:
    """
    获取DashScope API密钥

    优先级:
    1. 环境变量 DASHSCOPE_API_KEY
    2. .env 文件中的 DASHSCOPE_API_KEY
    3. 返回 None

    Returns:
        Optional[str]: API密钥或None
    """
    # 首先尝试从环境变量获取
    api_key = os.getenv('DASHSCOPE_API_KEY')
    if api_key:
        return api_key

    # 尝试从.env文件获取
    try:
        from dotenv import load_dotenv
        load_dotenv()
        api_key = os.getenv('DASHSCOPE_API_KEY')
        if api_key:
            return api_key
    except ImportError:
        pass  # dotenv模块未安装，跳过

    return None


def set_api_key(api_key: str) -> None:
    """
    设置DashScope API密钥到环境变量

    Args:
        api_key (str): API密钥
    """
    os.environ['DASHSCOPE_API_KEY'] = api_key


# 为了兼容性，保持原有的变量名
api_key = get_api_key()