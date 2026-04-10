import ipaddress
import re
from typing import Any
import requests

from .constants import FUNCTION_MAP

from .client import get_msg_count

def is_valid_ip(ip: str) -> bool:
    if ip is None or ip.strip() == "":
        return False
    if not re.match(r'^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$', ip):
        return False
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

# 判断接口是否能访问
def is_accessible(ip: str) -> bool:
    try:
        msg_count = get_msg_count(ip)
        return msg_count >= 0
    except Exception:
        return False

def load_models(base_url: str) -> list[str]:
    if not base_url:
        return []

    try:
        res = requests.get(f"{base_url}/v1/models", timeout=3)
        return [model["id"] for model in res.json()["data"]]
    except Exception as e:

        try:
            res = requests.get(f"https://api.jiekou.ai/openai/v1/models", timeout=3)
            return [model["id"] for model in res.json()["data"]]
        except Exception as e:
            return []

def execute_tool(func_name: str, args: dict) -> Any:
    func = FUNCTION_MAP[func_name]
    return func(**args)