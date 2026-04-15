

from functools import lru_cache
from typing import Tuple
from anthropic import AsyncAnthropic


anthropic_client = AsyncAnthropic(
    api_key="sk_EMCkI-4qXUXj2CkXG-Y6_yat65djagHfBQK0oCWhd14", 
    base_url="https://api.jiekou.ai/anthropic"
)


@lru_cache(maxsize=64)
def _cached_client(api_key: str, base_url: str) -> AsyncAnthropic:
    """以 (api_key, base_url) 为 key 缓存 client 实例，避免重复创建。"""
    return AsyncAnthropic(
        api_key=api_key,
        base_url=base_url,
    )

def get_anthropic_client(
    api_key: str | None = None,
    base_url: str | None = None,
) -> Tuple[bool, AsyncAnthropic]:
    """根据参数决定返回默认 client 还是用户自定义 client。"""

    if api_key and base_url:
        return True, _cached_client(api_key, base_url)

    return False, anthropic_client